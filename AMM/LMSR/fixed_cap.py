import math
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


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
    fees: float  # unused here, kept for parity


@dataclass
class Quote:
    yes_price: float
    no_price: float
    max_size: float


def round_figure(x: float, prec: int = 2) -> float:
    return round(x, prec)


def warning_msg(msg: str):
    # print(f"[WARNING] {msg}")
    pass

def mm_fee(amount: float, fee_perc: float) -> float:
    return int(amount * (fee_perc/ 100.0))

class LMSRContract:
    contract_id: int
    name: str
    risk_cap: float
    q_T: float  # shares for YES
    q_F: float  # shares for NO
    expected_yes_cashout: float
    expected_no_cashout: float
    fees: float
    order_history: List[Order]
    yes_deposits: float
    no_deposits: float

    def __init__(
        self,
        contract_id_: int,
        name_: str,
        risk_cap_: float,
        q_T_: float = 0.0,
        q_F_: float = 0.0,
        fees_: float = 0.0,
    ):
        self.contract_id = contract_id_
        self.name = name_
        self.risk_cap = risk_cap_
        self.q_T = q_T_          # shares for YES
        self.q_F = q_F_          # shares for NO

        self.fees = fees_
        self.order_history = []
        self.expected_no_cashout = 0.0
        self.expected_yes_cashout = 0.0
        self.yes_deposits = 0.0
        self.no_deposits = 0.0

        # LMSR parameter: b = R / log(2), where R = risk_cap
        self.b = risk_cap_ / math.log(2)

        # Thread safety
        self._lock = threading.Lock()
    


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
            price=price,  # price is now tracked here
            expected_cashout=cashout,
            side=side,
            fees=self.fees
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
            Side.NO:  exp_F / total,
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
        # Expand high exponentially
        for _ in range(60):
            new_cost = self.cost(self.q_T + high, self.q_F + high)
            if new_cost - base_cost >= remaining_risk:
                break
            high *= 2.0

        # Binary search
        for _ in range(60):
            mid = 0.5 * (low + high)
            new_cost = self.cost(self.q_T + mid, self.q_F + mid)
            if new_cost - base_cost < remaining_risk:
                low = mid
            else:
                high = mid

        dq = 0.5 * (low + high)

        # Convert dq to max stake at current mid-price
        p = self.price()
        p_self = p[Side.YES]  # symmetric; YES or NO yields same stake
        max_stake_val = self.b * p_self * (math.exp(dq / self.b) - 1.0)
        return max_stake_val



    # ---------------- Trade Execution ----------------
    def buy(self, side: Side, stake: float) -> Order:
        with self._lock:
            current_loss = self.cost(self.q_T, self.q_F) - self.cost(0.0, 0.0)
            remaining_risk = self.risk_cap - current_loss
            if remaining_risk <= 0:
                warning_msg("Market has reached risk capacity. Order ignored.")
                return Order(contract_id=self.contract_id, stake=0, price=0, expected_cashout=0, side=side, fees=0.0)

            prices = self.price()
            p_self = prices[Side.YES] if side == Side.YES else prices[Side.NO]
            max_allowed = self.max_stake()
            if stake > max_allowed:
                warning_msg(
                    f"Stake: ${round_figure(stake)} exceeds max allowed: ${round_figure(max_allowed)} for this market. Order ignored."
                )
                return Order(contract_id=self.contract_id, stake=0, price=0, expected_cashout=0, side=side, fees=0.0)

            # Exact delta_q: dq = b * log(1 + stake / (b * p_self))
            delta_q = self.b * math.log(1 + stake / (self.b * p_self))

            if side == Side.YES:
                self.q_T += delta_q
            else:
                self.q_F += delta_q

            # Recompute price
            prices = self.price()
            side_price = prices[Side.YES] if side == Side.YES else prices[Side.NO]

            expected_cashout = round_figure(stake / side_price)
            rounded_price = round_figure(side_price)

            order = Order(
                contract_id=self.contract_id,
                stake=stake,
                price=rounded_price,
                expected_cashout=expected_cashout,
                side=side,
                fees=self.fees
            )

            self.__update_inventory(side, stake, expected_cashout, side_price)

            return order

    # ---------------- Pull realtime quote ----------------
    def generate_quote(self) -> Quote:
        with self._lock:
            p = self.price()
            max_size = self.max_stake()
            return Quote(
                yes_price=round_figure(p[Side.YES]),
                no_price=round_figure(p[Side.NO]),
                max_size=round_figure(max_size)
            )

    # ---------------- Solve delta_q for given stake (fallback/legacy — not used in buy()) ----------------
    def solve_delta_q(self, side: Side, money: float) -> float:
        low, high = 0.0, 1.0
        # Expand high
        for _ in range(60):
            if side == Side.YES:
                cost_inc = self.cost(self.q_T + high, self.q_F) - self.cost(self.q_T, self.q_F)
            else:
                cost_inc = self.cost(self.q_T, self.q_F + high) - self.cost(self.q_T, self.q_F)
            if cost_inc >= money:
                break
            high *= 2.0

        # Binary search
        for _ in range(60):
            mid = 0.5 * (low + high)
            if side == Side.YES:
                cost_inc = self.cost(self.q_T + mid, self.q_F) - self.cost(self.q_T, self.q_F)
            else:
                cost_inc = self.cost(self.q_T, self.q_F + mid) - self.cost(self.q_T, self.q_F)

            if cost_inc < money:
                low = mid
            else:
                high = mid

        return 0.5 * (low + high)
    


if __name__ == "__main__":
    # Example usage
    contract = LMSRContract(contract_id_=1, name_="Will it rain tomorrow?", risk_cap_=100_000.0, fees_=2.0)
    quote = contract.generate_quote()
    print(f"Updated Quote: YES Price: {quote.yes_price}, NO Price: {quote.no_price}, Max Size: {quote.max_size}")

    import random

    _min, _max = 25, 500
    max_order = contract.max_stake()
    while max_order > _min:
        stake = random.uniform(_min, _max)
        side = random.choice([Side.YES, Side.NO])
        order = contract.buy(side=side, stake=stake)
        max_order = contract.max_stake()

    
    total_deposits = contract.yes_deposits + contract.no_deposits
    price = contract.price()
    # metrics
    print("Remaining Stake Capacity:", contract.max_stake())
    print("Final Prices:", {Side.YES.value: price[Side.YES], Side.NO.value: price[Side.NO]})
    print(f"Count: (YES: {len([o for o in contract.order_history if o.side == Side.YES])}, NO: {len([o for o in contract.order_history if o.side == Side.NO])})")
    print(f"Total Deposits: {int(total_deposits):,.2f}")
    print(f"Total YES Deposits: {int(contract.yes_deposits):,.2f}")
    print(f"Total NO Deposits: {int(contract.no_deposits):,.2f}")
    print(f"Total Orders: {len(contract.order_history)}")
    print(f"Final YES Cashout Liability: {int(contract.expected_yes_cashout):,.2f}")
    print(f"Final NO Cashout Liability: {int(contract.expected_no_cashout):,.2f}")
    yess_fee = mm_fee(contract.expected_yes_cashout, contract.fees)
    no_fee = mm_fee(contract.expected_no_cashout, contract.fees)
    print(f"Potential Fee Accurued (YES) : {yess_fee:,.2f} | (NO) : {no_fee:,.2f}")
    print(f"Expected Pnl before fee (YES) : {int(total_deposits - contract.expected_yes_cashout):,.2f} | (NO) : {int(total_deposits - contract.expected_no_cashout):,.2f}")
    print(f"Expected Pnl after fee (YES) : {int((total_deposits - contract.expected_yes_cashout) + yess_fee):,.2f} | (NO) : {int((total_deposits - contract.expected_no_cashout) + no_fee):,.2f}")


    print("\n\n------------------ Order History ----------------------------")
    for order in contract.order_history:
        print(f"Stake: {order.stake:,.2f}, Side: {order.side.value}, Price: {order.price:,.2f}, Cashout: {order.expected_cashout:,.2f}")
