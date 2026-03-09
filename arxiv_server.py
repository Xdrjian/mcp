from mcp.server.fastmcp import FastMCP
import httpx
import xml.etree.ElementTree as ET

# 初始化我们的“服务生”
mcp = FastMCP("Arxiv-Paper-Searcher")

@mcp.tool()
async def search_arxiv_papers(keyword: str, sort_by: str = "relevance") -> str:
    """
    从 arXiv 数据库搜索学术论文。
    
    参数:
    - keyword: 搜索关键词 (例如 "machine learning", "quantum computing")
    - sort_by: 排序方式。支持以下三种：
        1. "relevance" (按相关性排序，默认)
        2. "lastUpdatedDate" (按最新更新时间排序)
        3. "submittedDate" (按提交时间排序)
    """
    
    # arXiv API 官方文档规定的请求 URL 和参数
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{keyword}",
        "sortBy": sort_by,
        "sortOrder": "descending", # 默认降序，把最相关/最新的排前面
        "max_results": 10          # 严格限制只取前 10 篇
    }

    # 发起真实的 HTTP 请求
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
        except Exception as e:
            return f"请求 arXiv API 失败: {str(e)}"

        # 核心翻译逻辑：arXiv 返回的是古老的 XML (Atom 格式)，我们要把它解开
        root = ET.fromstring(response.text)
        
        # XML 命名空间处理
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entries = root.findall('atom:entry', ns)
        if not entries:
            return f"未找到与 '{keyword}' 相关的论文。"

        # 整理输出结果
        formatted_results = []
        for i, entry in enumerate(entries):
            # 提取标题、链接和摘要，并清理多余的换行符
            title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
            link = entry.find('atom:id', ns).text
            summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
            
            # 为了防止内容过长撑爆 Agent 上下文，只截取摘要的前 200 个字符
            truncated_summary = summary[:200] + "..." if len(summary) > 200 else summary
            
            paper_text = f"[{i+1}] 标题: {title}\n链接: {link}\n摘要: {truncated_summary}"
            formatted_results.append(paper_text)

        # 把 10 篇论文用双换行符拼接成一整段长文本，交给 FastMCP 去打包
        return "\n\n".join(formatted_results)

if __name__ == "__main__":
    # 默认通过 Stdio (标准输入输出) 启动服务
    mcp.run()