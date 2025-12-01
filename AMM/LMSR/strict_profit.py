import math
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple


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
    fees: float


@dataclass
class Quote:
    yes_price: float
    no_price: float
    max_yes_size: float
    max_no_size: float


def round_figure(x: float, prec: int = 2) -> float:
    return round(x, prec)


def warning_msg(msg: str):
    pass  # or print(f"[WARNING] {msg}")


class LMSRContract:
    def __init__(
        self,
        contract_id_: int,
        name_: str,
        risk_cap_: float,
        q_T_: float = 0.0,
        q_F_: float = 0.0,
        fee_rate_: float = 0.02,        # 2% fee
        skew_factor_: float = 0.01,     # inventory skew intensity
    ):
        self.contract_id = contract_id_
        self.name = name_
        self.risk_cap = risk_cap_
        self.q_T = q_T_
        self.q_F = q_F_

        self.fee_rate = fee_rate_        # e.g., 0.02 for 2%
        self.skew_factor = skew_factor_  # e.g., 0.01 = 1% skew per unit imbalance

        self.order_history: List[Order] = []
        self.expected_yes_cashout = 0.0
        self.expected_no_cashout = 0.0
        self.yes_deposits = 0.0
        self.no_deposits = 0.0

        self.b = risk_cap_ / math.log(2)
        self._lock = threading.Lock()

    @property
    def total_deposits(self) -> float:
        return self.yes_deposits + self.no_deposits

    def __update_inventory(self, side: Side, stake: float, cashout: float, price: float):
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
            fees=self.fee_rate * cashout  # optional: track per-order fee
        ))

    def cost(self, qT: float, qF: float) -> float:
        m = max(qT, qF)
        return self.b * (m / self.b + math.log(math.exp((qT - m) / self.b) + math.exp((qF - m) / self.b)))

    def price(self) -> Dict[Side, float]:
        m = max(self.q_T, self.q_F)
        exp_T = math.exp((self.q_T - m) / self.b)
        exp_F = math.exp((self.q_F - m) / self.b)
        p_yes_raw = exp_T / (exp_T + exp_F)
        p_no_raw = 1 - p_yes_raw

        total_q = self.q_T + self.q_F
        if total_q > 1e-6:
            imbalance = (self.q_T - self.q_F) / total_q  # +1: overexposed to YES
            # Skew: reduce price of overexposed side (make it less attractive)
            p_yes_skewed = p_yes_raw - self.skew_factor * imbalance
            # Clamp to [0.01, 0.99] to avoid degenerate odds
            p_yes_skewed = max(0.01, min(0.99, p_yes_skewed))
            p_no_skewed = 1 - p_yes_skewed
        else:
            p_yes_skewed, p_no_skewed = p_yes_raw, p_no_raw

        return {Side.YES: p_yes_skewed, Side.NO: p_no_skewed}

    def max_stake_for_side(self, side: Side) -> float:
        # 1. Global risk check
        base_cost = self.cost(self.q_T, self.q_F)
        initial_cost = self.cost(0.0, 0.0)
        current_loss = base_cost - initial_cost
        remaining_risk = self.risk_cap - current_loss
        if remaining_risk <= 0:
            return 0.0

        # 2. Directional risk: limit inventory imbalance
        # Allow up to, say, 20% of total liquidity in net exposure
        total_q = self.q_T + self.q_F
        net_q = abs(self.q_T - self.q_F)
        if total_q > 0 and net_q / total_q > 0.2:  # >20% imbalance
            # Only allow trades that *reduce* imbalance
            if (side == Side.YES and self.q_T > self.q_F) or \
            (side == Side.NO and self.q_F > self.q_T):
                return 0.0  # reject same-side bets

        # 3. Approximate max stake for this side using remaining risk
        # For single-side trade: ΔC ≈ stake (by design of LMSR)
        # So max stake ≈ remaining_risk (conservative)
        # But refine: use current price for better estimate
        p = self.price()
        p_self = p[side]
        # dq = b * log(1 + stake / (b * p_self)) → stake = b * p_self * (exp(dq/b) - 1)
        # But for small dq, exp(dq/b)−1 ≈ dq/b → stake ≈ p_self * dq
        # And ΔC ≈ dq * (1 - p_self) ??? → simpler: just use remaining_risk directly
        return remaining_risk  # ✅ safe upper bound

    def buy(self, side: Side, stake: float) -> Order:
        with self._lock:
            # Global risk check (LMSR worst-case)
            current_loss = self.cost(self.q_T, self.q_F) - self.cost(0.0, 0.0)
            if current_loss >= self.risk_cap:
                return Order(self.contract_id, 0, 0, 0, side, 0.0)

            prices = self.price()
            p_self = prices[side]
            max_allowed = self.max_stake_for_side(side)
            if stake > max_allowed:
                return Order(self.contract_id, 0, 0, 0, side, 0.0)

            # Execute trade
            delta_q = self.b * math.log(1 + stake / (self.b * p_self))
            if side == Side.YES:
                self.q_T += delta_q
            else:
                self.q_F += delta_q

            # Update state
            new_prices = self.price()
            side_price = new_prices[side]
            gross_cashout = stake / side_price
            # Apply fee at resolution (not here), so track gross for now
            rounded_price = round_figure(side_price)
            rounded_cashout = round_figure(gross_cashout)

            order = Order(
                contract_id=self.contract_id,
                stake=stake,
                price=rounded_price,
                expected_cashout=rounded_cashout,
                side=side,
                fees=0.0  # fees applied at resolution
            )
            self.__update_inventory(side, stake, rounded_cashout, side_price)
            return order

    def generate_quote(self) -> Quote:
        with self._lock:
            p = self.price()
            return Quote(
                yes_price=round_figure(p[Side.YES]),
                no_price=round_figure(p[Side.NO]),
                max_yes_size=round_figure(self.max_stake_for_side(Side.YES)),
                max_no_size=round_figure(self.max_stake_for_side(Side.NO))
            )

    def resolve(self, outcome: Side) -> Tuple[float, float]:
        """Returns (net_payout, fee_collected)"""
        gross_payout = (
            self.expected_yes_cashout if outcome == Side.YES else self.expected_no_cashout
        )
        fee_collected = gross_payout * self.fee_rate
        net_payout = gross_payout - fee_collected
        pnl = self.total_deposits - net_payout
        return net_payout, fee_collected, pnl


# ---------------- Demo ----------------
if __name__ == "__main__":
    import random
    contract = LMSRContract(
        contract_id_=1,
        name_="Will it rain tomorrow?",
        risk_cap_=100_000.0,
        fee_rate_=0.02,      # 2% fee
        skew_factor_=0.01,
    )

    quote = contract.generate_quote()
    print(f"Initial Quote: YES {quote.yes_price:.4f} / NO {quote.no_price:.4f} | "
          f"Max YES: ${quote.max_yes_size:,.0f}, Max NO: ${quote.max_no_size:,.0f}")


    accepted = 0
    for i in range(500):
        stake = random.uniform(25, 500)
        side = random.choice([Side.YES, Side.NO])
        order = contract.buy(side, stake)
        if order.stake > 0:
            accepted += 1

    print(f"\nAccepted {accepted}/500 orders.")

    if contract.total_deposits == 0:
        print("\n No trades accepted — check max_stake logic.")
    else:
        quote = contract.generate_quote()
        print(f"\nFinal Quote: YES {quote.yes_price:.4f} / NO {quote.no_price:.4f}")
        print(f"Total Deposits: ${contract.total_deposits:,.0f}")
        print(f"YES Liab: ${contract.expected_yes_cashout:,.0f} | NO Liab: ${contract.expected_no_cashout:,.0f}")
        
        imbalance_pct = (
            (contract.yes_deposits - contract.no_deposits) / contract.total_deposits
            if contract.total_deposits > 0 else 0.0
        )
        print(f"Imbalance: {imbalance_pct:+.1%}")

        # Simulate resolution
        for outcome in [Side.YES, Side.NO]:
            gross = contract.expected_yes_cashout if outcome == Side.YES else contract.expected_no_cashout
            fees = gross * contract.fee_rate
            net_payout = gross - fees
            pnl = contract.total_deposits - net_payout
            print(f"\nIf {outcome.value} wins:")
            print(f"  Gross Payout: ${gross:,.0f}")
            print(f"  Fees Collected: ${fees:,.0f}")
            print(f"  Net Payout: ${net_payout:,.0f}")
            print(f"  MM PnL: ${pnl:,.0f} ({pnl/contract.total_deposits:+.2%})")