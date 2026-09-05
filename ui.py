# =========================================
# Queen UI
# =========================================

class C:
    R = "\033[91m"       # Red
    Y = "\033[92m"       # Green
    C = "\033[93m"       # Yellow
    W = "\033[38;5;220m" # Gold
    B = "\033[94m"       # Blue
    P = "\033[95m"       # Pink
    U = "\033[96m"       # Cyan
    O = "\033[38;5;214m" # Orange
    K = "\033[97m"       # White
    X = "\033[0m"        # Reset

# PRINT
def p(color, text):
    print(color + str(text) + C.X)

# BANNER
def banner(title):
    p(C.Y, "===================================")
    p(C.W, f"       {title}")
    p(C.Y, "===================================")
