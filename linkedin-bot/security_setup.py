import requests
import json
import sys

TOKEN = "8760269302:AAEGQQFUJcn6r6nj8uDQ3KHJaZFuGR9cQ0w"
CHAT_ID = 1269463419
BASE = f"https://api.telegram.org/bot{TOKEN}"

def api(method, data=None):
    if data:
        r = requests.post(f"{BASE}/{method}", json=data, timeout=10)
    else:
        r = requests.get(f"{BASE}/{method}", timeout=10)
    return r.json()

print("=" * 50)
print("TELEGRAM BOT SECURITY SETUP")
print("=" * 50)

# 1. Get bot info
print("\n[1] BOT INFO:")
info = api("getMe")
if info.get("ok"):
    bot = info["result"]
    print(f"  Name     : {bot.get('first_name')}")
    print(f"  Username : @{bot.get('username')}")
    print(f"  Bot ID   : {bot.get('id')}")
    print(f"  Can join groups: {bot.get('can_join_groups')}")
    print(f"  Can read all msgs: {bot.get('can_read_all_group_messages')}")
else:
    print(f"  ERROR: {info}")
    sys.exit(1)

# 2. Get current default commands (visible to ALL users)
print("\n[2] CURRENT DEFAULT COMMANDS (visible to everyone):")
cmds = api("getMyCommands")
if cmds.get("result"):
    for c in cmds["result"]:
        print(f"  /{c['command']} - {c['description']}")
else:
    print("  None set")

# 3. DELETE commands from ALL scopes (so strangers see nothing)
print("\n[3] REMOVING commands from all public scopes...")
scopes = [
    {"type": "default"},
    {"type": "all_private_chats"},
    {"type": "all_group_chats"},
    {"type": "all_chat_administrators"},
]
for scope in scopes:
    r = api("deleteMyCommands", {"scope": scope})
    status = "OK" if r.get("result") else f"FAIL: {r}"
    print(f"  Scope '{scope['type']}': {status}")

# 4. SET commands ONLY for owner's specific chat (invisible to others)
print("\n[4] SETTING commands only for your private chat...")
owner_commands = [
    {"command": "post", "description": "Generate new LinkedIn post"},
    {"command": "last", "description": "Show last generated post"},
    {"command": "help", "description": "Show help"},
]
r = api("setMyCommands", {
    "commands": owner_commands,
    "scope": {"type": "chat", "chat_id": CHAT_ID}
})
status = "OK" if r.get("result") else f"FAIL: {r}"
print(f"  Owner chat commands set: {status}")

# 5. Verify - check owner commands
print("\n[5] VERIFYING owner commands:")
r = api("getMyCommands", {"scope": {"type": "chat", "chat_id": CHAT_ID}})
for c in r.get("result", []):
    print(f"  /{c['command']} - {c['description']}")

# 6. Verify default is now empty
print("\n[6] VERIFYING default commands (should be empty):")
r = api("getMyCommands")
result = r.get("result", [])
if not result:
    print("  CONFIRMED: No commands visible to strangers")
else:
    print(f"  WARNING: Still has commands: {result}")

print("\n" + "=" * 50)
print("SUMMARY:")
print("  Bot username visibility: Telegram cannot fully hide")
print("  bot usernames - but code-level filtering blocks all")
print("  unauthorized users regardless of how they find the bot.")
print("  Commands autocomplete: HIDDEN from strangers")
print("  Message handling: Will be blocked in bot.py (see next step)")
print("=" * 50)
