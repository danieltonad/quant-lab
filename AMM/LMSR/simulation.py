import random
import math
from datetime import datetime, timedelta
from lmsr import LMSRContract, Side, UserPortfolio

def fmt(x, prec=2):
    return f"{x:,.{prec}f}"

def mm_report(contract: LMSRContract, step: int = None) -> str:
    """Detailed MM risk & P&L report (what would happen if resolved now)"""
    q = contract.generate_quote()
    deposits = contract.yes_deposits + contract.no_deposits
    worst_payout = max(contract.q_T, contract.q_F)
    best_payout = min(contract.q_T, contract.q_F)
    
    # P&L if YES resolves
    pnl_yes = deposits - contract.q_T + contract.total_fees_collected
    # P&L if NO resolves
    pnl_no = deposits - contract.q_F + contract.total_fees_collected
    # Current "fair" expected P&L (using mid price)
    p_yes = q.yes_bid + (q.yes_ask - q.yes_bid) / 2
    expected_pnl = deposits - (p_yes * contract.q_T + (1 - p_yes) * contract.q_F) + contract.total_fees_collected
    
    risk_used = (contract.cost(contract.q_T, contract.q_F) - contract.cost(0, 0)) / contract.risk_cap * 100

    header = f"MM Report {f'(Step {step})' if step else ''}"
    return (
        f"\n{header}\n{'='*len(header)}\n"
        f"Prices: YES [{q.yes_bid:.3f} | {q.yes_ask:.3f}]  NO [{q.no_bid:.3f} | {q.no_ask:.3f}]\n"
        f"Inventory: YES={fmt(contract.q_T)} | NO={fmt(contract.q_F)}\n"
        f"Deposits: ${fmt(deposits)} | Fees: ${fmt(contract.total_fees_collected)}\n"
        f"Worst-Case Payout: ${fmt(worst_payout)} (if {Side.YES if contract.q_T > contract.q_F else Side.NO} wins)\n"
        f"Best-Case Payout:  ${fmt(best_payout)} (if {Side.NO if contract.q_T > contract.q_F else Side.YES} wins)\n"
        f"P&L if YES: ${fmt(pnl_yes)} | if NO: ${fmt(pnl_no)}\n"
        f"Expected P&L: ${fmt(expected_pnl)} (mid-price weighted)\n"
        f"Risk Used: {risk_used:.1f}% of ${fmt(contract.risk_cap)} cap\n"
    )

def simulate_users(contract: LMSRContract, n_users: int = 5, n_trades: int = 30):
    users = [UserPortfolio(f"user_{i:02d}") for i in range(1, n_users + 1)]
    sides = [Side.YES, Side.NO]
    actions = ['buy', 'sell']
    
    print(f"Starting simulation: {n_users} users, {n_trades} trades")
    print(mm_report(contract, step=0))
    
    for step in range(1, n_trades + 1):
        user = random.choice(users)
        side = random.choice(sides)
        
        # Determine action: can only sell if owns shares
        owned = user.yes_shares if side == Side.YES else user.no_shares
        possible_actions = ['buy']
        if owned > 1.0:  # min 1 share to sell
            possible_actions.append('sell')
        action = random.choice(possible_actions)
        
        # Size: log-uniform between $10 and $5,000
        stake_or_shares = math.exp(random.uniform(math.log(10), math.log(5000)))
        
        try:
            if action == 'buy':
                order = user.buy(contract, side, stake=stake_or_shares)
                desc = f"{user.user_id} BUY {side.value} ${fmt(order.stake)}"
            else:  # sell
                shares_to_sell = min(owned, stake_or_shares / 10)  # sell portion
                if shares_to_sell < 0.1:
                    continue
                order = user.sell(contract, side, shares=shares_to_sell)
                desc = f"{user.user_id} SELL {side.value} {fmt(order.expected_cashout)} shares"
            
            # Log trade
            print(f"\n[{step:2d}] {desc}")
            print(f"    → Price: {order.price:.3f} | Fee: ${fmt(order.fees)} | "
                  f"User {user.user_id} bal: YES={fmt(user.yes_shares)} NO={fmt(user.no_shares)}")
            
            # Show MM report every 5 trades (or last)
            if step % 5 == 0 or step == n_trades:
                print(mm_report(contract, step=step))
                
        except Exception as e:
            # Skip invalid trades (e.g., slippage errors)
            continue

    # Final summary
    print("\n" + "="*60)
    print("SIMULATION COMPLETE — MM FINAL POSITION")
    print("="*60)
    print(mm_report(contract))
    
    # Top user P&L (unrealized)
    print("\nTop 3 Users (Unrealized P&L if YES):")
    user_pnls = []
    for u in users:
        if u.yes_shares + u.no_shares > 0:
            # Unrealized P&L if YES happens
            pnl_yes = u.net_cash + u.yes_shares
            user_pnls.append((u.user_id, pnl_yes, u.net_cash, u.yes_shares, u.no_shares))
    
    user_pnls.sort(key=lambda x: x[1], reverse=True)
    for i, (uid, pnl, cash, yes, no) in enumerate(user_pnls[:3]):
        print(f"{i+1}. {uid}: P&L=${fmt(pnl)} | Cash=${fmt(cash)} | YES={fmt(yes)} | NO={fmt(no)}")


if __name__ == "__main__":
    
    contract = LMSRContract(
        contract_id_=1,
        name_="Will AI pass Turing Test by 2030?",
        risk_cap_=100_000.0,
        fee_percent_=1.5
    )
    
    simulate_users(contract, n_users=8, n_trades=50)