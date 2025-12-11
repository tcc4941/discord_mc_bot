import os
import discord
from discord.ext import commands
from wakeonlan import send_magic_packet
from mcstatus import JavaServer
from mcrcon import MCRcon
import paramiko
from ping3 import ping
from dotenv import load_dotenv
import time
import keep_alive

# 載入設定
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
HOST_MAC = os.getenv('HOST_MAC')
HOST_IP = os.getenv('HOST_IP')
HOST_PUBLIC_IP = os.getenv('HOST_PUBLIC_IP')
HOST_WOL_PORT = int(os.getenv('HOST_WOL_PORT'))
SSH_USER = os.getenv('SSH_USER')
SSH_PASSWORD = os.getenv('SSH_PASSWORD')
SSH_PORT = int(os.getenv('SSH_PORT'))
MC_RCON_HOST = os.getenv('MC_RCON_HOST')
MC_RCON_PORT = int(os.getenv('MC_RCON_PORT'))
MC_RCON_PAASSWORD = os.getenv('MC_RCON_PASSWORD')
MC_SERVER_PORT = int(os.getenv('MC_SERVER_PORT'))
MC_START_CMD = os.getenv('MC_START_CMD')

# WOL setup
RepeatingTimes = 10
IntervalTimerSec = 1

# discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def is_host_online():
    """檢查主機是否回應 Ping"""
    response = ping(HOST_PUBLIC_IP, timeout=2)
    return response is not None

# ssh setup
def ssh_execute(command):
    """透過 SSH連線到主機執行指令"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST_PUBLIC_IP, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD, timeout=5)
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        client.close()
        return True, output
    except Exception as e:
        return False, str(e)

# mc status setup
def get_mc_status():
    """查詢 Minecraft 伺服器狀態"""
    try:
        # 查詢內網 IP，若 Bot 在外部則改用 IP_PUBLIC
        server = JavaServer.lookup(f"{HOST_PUBLIC_IP}:{os.getenv('MC_SERVER_PORT', 25565)}")
        status = server.status()
        return True, f"🟢 線上 | 人數: {status.players.online}/{status.players.max} | 延遲: {round(status.latency)}ms"
    except:
        return False, "🔴 離線"
    
def send_rcon_command(command):
    """透過 RCON 發送指令給 Minecraft"""
    try:
        with MCRcon(HOST_PUBLIC_IP, MC_RCON_PAASSWORD, port=MC_RCON_PORT) as mcr:
            resp = mcr.command(command)
            return True, resp
    except Exception as e:
        return False, str(e)
    
# Bot Events
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def pc_on(ctx):
    """啟動主機 (WOL)"""
    for i in range(RepeatingTimes):
        send_magic_packet(HOST_MAC, ip_address=HOST_PUBLIC_IP, port=HOST_WOL_PORT)
        print('Send Magic Packet to ' + HOST_MAC)
        time.sleep(IntervalTimerSec)
        
    await ctx.send(f"⚡ 已發送魔術封包至 {HOST_MAC}，主機啟動中...")

@bot.command()
async def pc_off(ctx):
    """關閉主機"""
    if not is_host_online():
        await ctx.send("⚠️ 主機似乎已經離線。")
        return

    # Windows 關機指令
    success, msg = ssh_execute("shutdown /s /t 10")
    if success:
        await ctx.send("💤 已發送關機指令 (10秒後執行)。")
    else:
        await ctx.send(f"❌ 關機失敗: {msg}")

@bot.command()
async def pc_re(ctx):
    """重新啟動主機"""
    if not is_host_online():
        await ctx.send("⚠️ 主機似乎不在線上，無法重啟。")
        return

    # Windows 重啟指令
    success, msg = ssh_execute("shutdown /r /t 10")
    if success:
        await ctx.send("🔄 已發送重啟指令 (10秒後執行)。")
    else:
        await ctx.send(f"❌ 重啟失敗: {msg}")

@bot.command()
async def status(ctx):
    """顯示主機以及Minecraft伺服器狀態"""    
    # 檢查 MC
    mc_online, mc_msg = get_mc_status()
    
    embed = discord.Embed(title="伺服器狀態監控", color=0x00ff00)
    embed.add_field(name="⛏️ Minecraft", value=mc_msg, inline=False)
    embed.add_field(name="IP 資訊", value=f"WAN: {HOST_PUBLIC_IP}\nLAN: {HOST_IP}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def mc_on(ctx):
    """開啟主機內的Minecraft伺服器"""
    if not is_host_online():
        await ctx.send("⚠️ 主機未開機，請先執行 `!pc_on`")
        return

    mc_online, _ = get_mc_status()
    # if mc_online:
    #     await ctx.send("⚠️ Minecraft 伺服器已經在運作中！")
    #     return

    # 執行開啟腳本
    success, msg = ssh_execute(MC_START_CMD)
    if success:
        await ctx.send("🚀 已發送開服指令，請稍候約 30-60 秒...")
    else:
        await ctx.send(f"❌ 開服失敗 (SSH錯誤): {msg}")

@bot.command()
async def mc_off(ctx):
    """關閉主機內Minecraft伺服器"""
    await ctx.send("🛑 正在停止 Minecraft 伺服器...")
    
    # 先存檔
    send_rcon_command("save-all")
    time.sleep(1)
    
    # 發送停止指令
    success, resp = send_rcon_command("stop")
    if success:
        await ctx.send(f"✅ 伺服器已安全停止: {resp}")
    else:
        await ctx.send(f"❌ 停止失敗 (RCON錯誤): {resp}")

@bot.command()
async def mc_re(ctx):
    """重啟Minecraft伺服器"""
    await mc_off(ctx)
    await ctx.send("⏳ 等待 10 秒後重新啟動...")
    time.sleep(10)
    await mc_on(ctx)

if __name__ == '__main__':
    keep_alive.keep_alive()
    bot.run(DISCORD_TOKEN)
    
    
