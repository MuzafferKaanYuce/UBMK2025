import json, os
from mcp.server.fastmcp import FastMCP
from typing import List
from threading import Lock

DATA_PATH = r"C:\Users\Sots\Desktop\UBMK2025\Mcp-1\Data\employee_leaves.json"
_lock = Lock()

def _ensure_parent_dir(path: str) -> None:
    
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)

def load_data():
    
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Dosya bozuksa varsayılanla devam et
            pass
    # default başlangıç
    return {
        "E001": {"balance": 18, "history": ["2024-12-25", "2025-01-01"]},
        "E002": {"balance": 20, "history": []}
    }

def save_data(data):
    # Kayıttan önce oluştur
    _ensure_parent_dir(DATA_PATH)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

employee_leaves = load_data()
mcp = FastMCP("UBMK2025")

@mcp.tool()
def get_leave_balance(employee_id: str) -> str:
    data = employee_leaves.get(employee_id)
    if data:
        return f"{employee_id} has {data['balance']} leave days remaining."
    return "Employee ID not found."

@mcp.tool()
def apply_leave(employee_id: str, leave_dates: List[str]) -> str:
    with _lock:  # eşzamanlı çağrılara karşı
        if employee_id not in employee_leaves:
            return "Employee ID not found."

        requested_days = len(leave_dates)
        available_balance = employee_leaves[employee_id]["balance"]

        if available_balance < requested_days:
            return (f"Insufficient leave balance. You requested {requested_days} "
                    f"but have only {available_balance}.")

        # Güncelle ve KALICI yaz
        employee_leaves[employee_id]["balance"] -= requested_days
        employee_leaves[employee_id]["history"].extend(leave_dates)
        save_data(employee_leaves)

        return (f"Leave applied for {requested_days} day(s). Remaining balance: "
                f"{employee_leaves[employee_id]['balance']}.")

@mcp.tool()
def get_leave_history(employee_id: str) -> str:
    data = employee_leaves.get(employee_id)
    if data:
        history = ', '.join(data['history']) if data['history'] else "No leaves taken."
        return f"Leave history for {employee_id}: {history}"
    return "Employee ID not found."

@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    return f"Hello, {name}! How can I assist you with leave management today?"

if __name__ == "__main__":
    mcp.run()
