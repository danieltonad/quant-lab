import math
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List
from collections import defaultdict

class Side(Enum):
    YES = "YES"
    NO = "NO"


@dataclass
class Order:
    contract_id: int
    stake: float
    price: float
    expected_cashout: float
    side: Side
    fees: float  # Now included (was missing in your dataclass)


@dataclass
class Quote:
    yes_bid: float   # price to SELL YES (user receives this per $1 payout)
    yes_ask: float   # price to BUY YES (user pays this per $1 payout)
    no_bid: float
    no_ask: float
    max_buy_size: float
    max_sell_size: float  # may differ due to inventory skew


def round_figure(x: float, prec: int = 2) -> float:
    return round(x, prec)


def warning_msg(msg: str):
    # print(f"[WARNING] {msg}")
    pass


class LMSRContract:
    def __init__(
        self,
        contract_id_: int,
        name_: str,
        risk_cap_: float,
        q_T_: float = 0.0,
        q_F_: float = 0.0,
        fee_percent_: float = 2.0,
    ):
        self.contract_id = contract_id_
        self.name = name_
        self.risk_cap = risk_cap_
        self.q_T = q_T_          # shares for YES
        self.q_F = q_F_          # shares for NO

        self.fee_rate = fee_percent_ / 100.0
        self.total_fees_collected = 0.0

        self.order_history: List[Order] = []
        self.expected_yes_cashout = 0.0
        self.expected_no_cashout = 0.0
        self.yes_deposits = 0.0
        self.no_deposits = 0.0

        # LMSR parameter: b = R / log(2), where R = risk_cap
        self.b = risk_cap_ / math.log(2)

        # Thread safety
        self._lock = threading.Lock()

    def __update_inventory(self, side: Side, stake: float, cashout: float, price: float, fees: float):
        if side == Side.YES:
            self.expected_yes_cashout += cashout
            self.yes_deposits += stake
        else:
            self.expected_no_cashout += cashout
            self.no_deposits += stake

        self.order_history.append(Order(
            contract_id=self.contract_id,
            stake=stake,
            price=price,
            expected_cashout=cashout,
            side=side,
            fees=fees
        ))

    # ---------------- Cost function (log-sum-exp stabilized) ----------------
    def cost(self, qT: float, qF: float) -> float:
        m = max(qT, qF)
        return self.b * (m / self.b + math.log(math.exp((qT - m) / self.b) + math.exp((qF - m) / self.b)))

    # ---------------- Current price / odds ----------------
    def price(self) -> Dict[Side, float]:
        m = max(self.q_T, self.q_F)
        exp_T = math.exp((self.q_T - m) / self.b)
        exp_F = math.exp((self.q_F - m) / self.b)
        total = exp_T + exp_F
        return {
            Side.YES: exp_T / total,
            Side.NO: exp_F / total,
        }

    # ---------------- Compute max stake (risk capacity remaining) ----------------
    def max_stake(self) -> float:
        base_cost = self.cost(self.q_T, self.q_F)
        initial_cost = self.cost(0.0, 0.0)
        current_loss = base_cost - initial_cost
        remaining_risk = self.risk_cap - current_loss

        if remaining_risk <= 0:
            return 0.0

        # Binary search for dq such that cost(qT+dq, qF+dq) - cost(qT,qF) = remaining_risk
        low, high = 0.0, 1.0
        for _ in range(60):
            new_cost = self.cost(self.q_T + high, self.q_F + high)
            if new_cost - base_cost >= remaining_risk:
                break
            high *= 2.0

        for _ in range(60):
            mid = 0.5 * (low + high)
            new_cost = self.cost(self.q_T + mid, self.q_F + mid)
            if new_cost - base_cost < remaining_risk:
                low = mid
            else:
                high = mid

        dq = 0.5 * (low + high)
        p = self.price()
        p_self = p[Side.YES]
        max_stake_val = self.b * p_self * (math.exp(dq / self.b) - 1.0)
        return max_stake_val

    # ---------------- BUY Trade Execution ----------------
    def buy(self, side: Side, stake: float) -> Order:
        with self._lock:
            current_loss = self.cost(self.q_T, self.q_F) - self.cost(0.0, 0.0)
            remaining_risk = self.risk_cap - current_loss
            if remaining_risk <= 0:
                warning_msg("Market has reached risk capacity. Order ignored.")
                return Order(contract_id=self.contract_id, stake=0, price=0, expected_cashout=0, side=side, fees=0.0)

            prices = self.price()
            p_mid = prices[Side.YES] if side == Side.YES else prices[Side.NO]
            max_allowed = self.max_stake()
            if stake > max_allowed:
                warning_msg(
                    f"Stake: ${round_figure(stake)} exceeds max allowed: ${round_figure(max_allowed)} for this market. Order ignored."
                )
                return Order(contract_id=self.contract_id, stake=0, price=0, expected_cashout=0, side=side, fees=0.0)

            # User pays full stake; AMM receives stake * (1 - fee_rate)
            fee_amount = stake * self.fee_rate
            net_to_pool = stake - fee_amount
            self.total_fees_collected += fee_amount

            # Compute dq using net amount (what actually moves inventory)
            delta_q = self.b * math.log(1 + net_to_pool / (self.b * p_mid))

            if side == Side.YES:
                self.q_T += delta_q
            else:
                self.q_F += delta_q

            # Recompute price after trade
            new_prices = self.price()
            side_price = new_prices[Side.YES] if side == Side.YES else new_prices[Side.NO]

            # Expected cashout = shares = dq (face value if resolved YES/NO)
            expected_cashout = round_figure(delta_q)

            order = Order(
                contract_id=self.contract_id,
                stake=stake,
                price=round_figure(side_price),
                expected_cashout=expected_cashout,
                side=side,
                fees=round_figure(fee_amount)
            )

            self.__update_inventory(side, net_to_pool, expected_cashout, side_price, fee_amount)
            return order

    # ---------------- SELL Trade Execution ----------------
    def sell(self, side: Side, stake: float) -> Order:
        """
        User sells outcome shares.
        stake = desired *net cash to user* (after fees).
        """
        with self._lock:
            current_loss = self.cost(self.q_T, self.q_F) - self.cost(0.0, 0.0)
            remaining_risk = self.risk_cap - current_loss
            if remaining_risk <= 0:
                warning_msg("Market at risk capacity. Sell order ignored.")
                return Order(contract_id=self.contract_id, stake=0, price=0, expected_cashout=0, side=side, fees=0.0)

            max_allowed = self.max_stake()
            if stake > max_allowed:
                warning_msg(f"Sell stake ${round_figure(stake)} > max allowed ${round_figure(max_allowed)}. Ignored.")
                return Order(contract_id=self.contract_id, stake=0, price=0, expected_cashout=0, side=side, fees=0.0)

            # Gross amount AMM must pay from pool
            gross_from_pool = stake / (1.0 - self.fee_rate)
            fee_amount = gross_from_pool * self.fee_rate
            self.total_fees_collected += fee_amount

            # Solve for dq such that: C(q) - C(q - dq) = gross_from_pool
            def cost_diff(dq: float) -> float:
                if side == Side.YES:
                    return self.cost(self.q_T, self.q_F) - self.cost(self.q_T - dq, self.q_F)
                else:
                    return self.cost(self.q_T, self.q_F) - self.cost(self.q_T, self.q_F - dq)

            low, high = 0.0, max(1.0, gross_from_pool * 2)
            for _ in range(60):
                if cost_diff(high) >= gross_from_pool:
                    break
                high *= 2.0

            for _ in range(60):
                mid = 0.5 * (low + high)
                if cost_diff(mid) < gross_from_pool:
                    low = mid
                else:
                    high = mid
            dq = 0.5 * (low + high)

            # No shorting allowed
            if side == Side.YES:
                if dq > self.q_T + 1e-9:
                    warning_msg("Cannot sell more YES shares than outstanding. Order ignored.")
                    return
                self.q_T -= dq
            else:
                if dq > self.q_F + 1e-9:
                    warning_msg("Cannot sell more NO shares than outstanding. Order ignored.")
                    return 
                self.q_F -= dq

            # New marginal price
            new_prices = self.price()
            side_price = new_prices[Side.YES] if side == Side.YES else new_prices[Side.NO]
            expected_cashout = round_figure(dq)  # shares sold

            order = Order(
                contract_id=self.contract_id,
                stake=stake,  # net to user
                price=round_figure(side_price),
                expected_cashout=expected_cashout,
                side=side,
                fees=round_figure(fee_amount)
            )

            self.__update_inventory(side, -gross_from_pool, -expected_cashout, side_price, fee_amount)
            return order

    # ---------------- Pull realtime quote ----------------
    def generate_quote(self) -> Quote:
        with self._lock:
            p = self.price()
            p_yes = p[Side.YES]
            p_no = p[Side.NO]
            max_size = self.max_stake()

            yes_ask = min(1.0, p_yes / (1.0 - self.fee_rate))
            yes_bid = max(0.0, p_yes * (1.0 - self.fee_rate))
            no_ask = min(1.0, p_no / (1.0 - self.fee_rate))
            no_bid = max(0.0, p_no * (1.0 - self.fee_rate))

            return Quote(
                yes_bid=round_figure(yes_bid),
                yes_ask=round_figure(yes_ask),
                no_bid=round_figure(no_bid),
                no_ask=round_figure(no_ask),
                max_buy_size=round_figure(max_size),
                max_sell_size=round_figure(max_size)
            )

    # ---------------- Solve delta_q (fallback) ----------------
    def solve_delta_q(self, side: Side, money: float) -> float:
        low, high = 0.0, 1.0
        for _ in range(60):
            cost_inc = self.cost(
                self.q_T + (high if side == Side.YES else 0.0),
                self.q_F + (high if side == Side.NO else 0.0)
            ) - self.cost(self.q_T, self.q_F)
            if cost_inc >= money:
                break
            high *= 2.0

        for _ in range(60):
            mid = 0.5 * (low + high)
            cost_inc = self.cost(
                self.q_T + (mid if side == Side.YES else 0.0),
                self.q_F + (mid if side == Side.NO else 0.0)
            ) - self.cost(self.q_T, self.q_F)
            if cost_inc < money:
                low = mid
            else:
                high = mid
        return 0.5 * (low + high)

    def get_pnl(self) -> Dict[str, float]:
        total_deposits = self.yes_deposits + self.no_deposits
        worst_case_payout = max(self.q_T, self.q_F)
        unrealized_pnl = total_deposits - worst_case_payout
        realized_pnl = self.total_fees_collected
        total_pnl = unrealized_pnl + realized_pnl
        risk_used = (self.cost(self.q_T, self.q_F) - self.cost(0.0, 0.0)) / self.risk_cap * 100
        return {
            "total_deposits": total_deposits,
            "worst_case_payout": worst_case_payout,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_pnl": total_pnl,
            "risk_used_pct": risk_used
        }
    


    def resolve(self, outcome: Side) -> Dict[str, float]:
        """
        Resolve the market and compute final payouts.
        Returns: {
            "outcome": str,
            "total_payout": float,
            "fees_collected": float,
            "net_pnl": float,
            "risk_cap_used_pct": float
        }
        """
        with self._lock:
            if hasattr(self, '_resolved') and self._resolved:
                raise RuntimeError("Contract already resolved")

            total_yes = self.q_T  # total YES shares outstanding (held by users)
            total_no = self.q_F   # total NO shares outstanding

            if outcome == Side.YES:
                total_payout = total_yes
                self._resolved_outcome = Side.YES
            else:
                total_payout = total_no
                self._resolved_outcome = Side.NO

            # MM's net cash inflow = total deposits - payout
            total_deposits = self.yes_deposits + self.no_deposits
            gross_pnl = total_deposits - total_payout
            net_pnl = gross_pnl + self.total_fees_collected

            self._resolved = True

            return {
                "outcome": outcome.value,
                "total_payout": round_figure(total_payout),
                "fees_collected": round_figure(self.total_fees_collected),
                "gross_pnl": round_figure(gross_pnl),
                "net_pnl": round_figure(net_pnl),
                "risk_cap_used_pct": round_figure(
                    (self.cost(self.q_T, self.q_F) - self.cost(0.0, 0.0)) / self.risk_cap * 100
                )
            }
        

    def get_resolution_summary(self) -> str:
        if not hasattr(self, '_resolved') or not self._resolved:
            return "⚠️ Contract not resolved yet"
        
        outcome = self._resolved_outcome
        payout = self.q_T if outcome == Side.YES else self.q_F
        deposits = self.yes_deposits + self.no_deposits
        fees = self.total_fees_collected
        
        return (
            f"RESOLVED: {outcome.value}\n"
            f"- Total Deposits: ${deposits:,.2f}\n"
            f"- Payout: ${payout:,.2f}\n"
            f"- Fees: ${fees:,.2f}\n"
            f"- MM Net P&L: ${deposits - payout + fees:,.2f}"
        )
    



















class UserPortfolio:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.yes_shares: float = 0.0
        self.no_shares: float = 0.0
        self.net_cash: float = 0.0  # negative = spent

    def buy(self, contract: LMSRContract, side: Side, stake: float) -> Order:
        order = contract.buy(side, stake)
        if side == Side.YES:
            self.yes_shares += order.expected_cashout
        else:
            self.no_shares += order.expected_cashout
        self.net_cash -= stake
        return order

    def sell(self, contract: LMSRContract, side: Side, shares: float) -> Order:
        # Enforce ownership
        owned = self.yes_shares if side == Side.YES else self.no_shares
        if shares > owned + 1e-6:
            raise ValueError(f"Insufficient {side} shares: {shares:.2f} requested, {owned:.2f} owned")

        # Convert shares → approximate cash using current bid
        quote = contract.generate_quote()
        bid = quote.yes_bid if side == Side.YES else quote.no_bid
        stake = shares * bid * (1 - contract.fee_rate)  # net to user

        order = contract.sell(side, stake)
        
        # Adjust for slippage (order.expected_cashout may ≠ shares)
        actual_shares = order.expected_cashout
        if side == Side.YES:
            self.yes_shares -= actual_shares
        else:
            self.no_shares -= actual_shares
        self.net_cash += order.stake
        return order

    def pnl_if_yes(self) -> float:
        return self.yes_shares + self.net_cash

    def pnl_if_no(self) -> float:
        return self.no_shares + self.net_cash
    
    def settle(self, outcome: Side) -> float:
        """
        Settle user's position after resolution.
        Returns final cash balance (including redemption).
        """
        if outcome == Side.YES:
            redemption = self.yes_shares
        else:
            redemption = self.no_shares
        
        final_balance = self.net_cash + redemption
        return round_figure(final_balance)