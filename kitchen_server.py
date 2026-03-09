import json
import os
import httpx
from mcp.server.fastmcp import FastMCP, Image

# 1. 初始化服务器
mcp = FastMCP("Kitchen-Assistant")

# 定义本地偏好文件的存储路径
PREFS_FILE = "preferences.json"

# ==========================================
# 抽象一：Resource (只读资源) - 被动档案
# ==========================================
@mcp.resource("file://preferences")
def read_preferences() -> str:
    """读取用户的饮食偏好档案"""
    # 如果文件不存在（首次运行），返回 not_set 状态
    if not os.path.exists(PREFS_FILE):
        return json.dumps({"status": "not_set", "message": "User has not set any preferences yet."})
    
    # 如果文件存在，读取并返回真实数据
    with open(PREFS_FILE, "r", encoding="utf-8") as f:
        return f.read()


# ==========================================
# 抽象二：Tool (工具) - 状态修改 (写操作)
# ==========================================
@mcp.tool()
def update_preferences(diet: str = "", allergies: list[str] = None, dislikes: list[str] = None) -> str:
    """
    更新或创建用户的饮食偏好、过敏原和忌口记录。
    Agent 会在询问用户后主动调用此工具写入数据。
    """
    allergies = allergies or []
    dislikes = dislikes or []
    
    prefs = {}
    # 如果已有记录，先读出来，在此基础上追加
    if os.path.exists(PREFS_FILE):
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            try:
                prefs = json.load(f)
            except json.JSONDecodeError:
                pass
    
    # 更新字段
    if diet: 
        prefs["diet"] = diet
    if allergies: 
        # 使用 set 去重后追加
        prefs["allergies"] = list(set(prefs.get("allergies", []) + allergies))
    if dislikes: 
        prefs["dislikes"] = list(set(prefs.get("dislikes", []) + dislikes))
    
    # 写回本地文件
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)
        
    return f"偏好已成功更新并保存至本地文件。当前状态: {json.dumps(prefs, ensure_ascii=False)}"


# ==========================================
# 抽象二：Tool (工具) - 视觉感知 (读操作)
# ==========================================
@mcp.tool()
async def look_into_fridge() -> Image:
    """
    打开冰箱看一眼。返回冰箱内部的实时照片。
    """
    # ⚠️ 请将这里替换为你刚才复制的 GitHub Raw 图片链接
    github_image_url = "https://raw.githubusercontent.com/Xdrjian/mcp/main/fridge.jpg"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(github_image_url)
        response.raise_for_status()
        
        # FastMCP 原生支持返回 Image 对象，Agent 收到后会自动激活多模态视觉能力
        return Image(data=response.content, format="jpeg")


# ==========================================
# 抽象三：Prompt (提示词) - 标准工作流模板
# ==========================================
@mcp.prompt()
def plan_dinner() -> str:
    """触发米其林大厨的晚餐规划工作流"""
    return """你是一位米其林三星主厨，现在要为我准备晚餐。请严格按照以下 SOP 步骤执行：

1. 首先，读取资源 `file://preferences` 获取我的饮食偏好档案。
2. 【关键分支】如果发现偏好状态是 `not_set`，请立刻停止后续动作！向我礼貌地询问我的忌口和饮食偏好（如高蛋白、无麸质、不吃香菜等）。
3. 当我回答了偏好后，或者如果你收到了我“不想吃xxx”的指令，你必须立刻调用 `update_preferences` 工具将它们持久化记录下来。
4. 确保偏好记录完毕后，调用 `look_into_fridge` 工具查看冰箱里现有的食材图片。
5. 结合我的偏好记录和冰箱里你能认出来的食材，为我量身定制一份详细的晚餐菜谱。"""


if __name__ == "__main__":
    mcp.run()
