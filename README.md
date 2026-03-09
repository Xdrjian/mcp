# MCP (Model Context Protocol) 学习笔记与实战总结

## 一、 MCP 技术核心逻辑综合总结

MCP 的本质是**将大语言模型（Agent 的大脑）与外部世界（工具、数据）解耦的标准化通信协议**。Agent 负责“自然语言理解与推理”，而 MCP Server（我们写的 Python 脚本）负责“规则路由与接口包装”。两者之间通过严格的 JSON-RPC 2.0 格式进行通信。

**MCP 的三大核心抽象：**

1. **Resources (资源)**：被动读取的“本地档案”。Agent 就像看说明书一样随时读取，不需要消耗推理步骤去“执行”获取动作。
2. **Tools (工具)**：主动执行的“网络抓手”或“状态修改器”。Agent 在遇到问题时，会基于工具的描述（说明书）自主决定何时调用。
3. **Prompts (提示词模板)**：为用户提供的一键化工作流标准模板。

> **我的个人理解总结：**
> “tool 结构的函数，Agent 会在启动时读取说明，并在合适的时候主动调用。而 prompt 结构的函数，是必须由用户指定调用的，属于是类似快捷键，Agent 本身不会知道这个 prompt 的存在。”

**解耦的魅力：**
无论 Agent 是 Cursor、Claude Desktop 还是其他宿主，大模型只管“点菜”（依靠聪明的语义理解提取参数），客户端负责“传菜”（跨 Server 路由寻找 Tool），Python 框架负责“做菜”（异步执行代码并打包返回）。

---

## 二、 核心疑惑与代码/语法细节剖析

在开发过程中，我遇到了一些看似是“黑魔法”的逻辑，梳理如下：

### 1. 装饰符 `@` 有什么用途？这是告诉 Agent 的吗？

* **实质**：这是纯 Python 语法（装饰器），Agent 完全不知道它的存在。
* **用途**：它告诉 FastMCP 框架，将下面的 Python 函数登记到“对外暴露工具名册”中。Python 启动时会扫描这些 `@`，打包成 JSON 格式的“说明书”发给 Agent。

### 2. 函数定义后的 `-> str` 是什么意义？

* **实质**：Python 3 的类型提示（Type Hint）。
* **用途**：框架利用 Python 的**反射机制**阅读这个标记。它告诉 Agent 契约内容：“调用这个工具后，你会收到纯文本 (str) 或图片 (Image)”。在 MCP 中这是必须写的，否则框架无法准确生成 JSON Schema。

### 3. Agent 怎么知道从我的话里提取参数（如“高蛋白”、“蘑菇”）？它读代码了吗？

* **实质**：Agent 绝对没有读 Python 代码，完全靠大语言模型强大的 Function Calling 理解能力。
* **机制**：FastMCP 在初始化时，通过反射把代码的参数类型转换成了 JSON Schema 格式发给了 Agent。Agent 听到自然语言后，自主分析出“高蛋白”对应 `diet` 参数，“蘑菇”对应 `dislikes` 参数，然后构造极其精确的 JSON-RPC 请求发给 Server。

### 4. 为什么通信的方法名叫 `"resources/read"`？可以把 URI 换成 `"pianhao123"` 吗？

* **机制来源**：`"resources/read"` 既不是 Python 变量也不是框架函数，它是 **MCP 协议官方规范写死的固定暗号（Method）**。
* **关于自定义 URI**：虽然 Python 字典匹配 `pianhao123` 没问题，但 **MCP 协议的底层校验会拦截它**，因为合法的 URI 必须带有协议头（Scheme）。
* **解决方案**：可以捏造一个专属协议头，如 `mcp-dict://pianhao123`。只要带有 `://`，协议警察就会放行，Python 字典也能完美匹配执行。这种设计体现了**“业务逻辑极其自由，但通信协议极其独裁”**的系统分层思想。

### 5. 跨 MCP Server 调用 Tool，Agent 能找到吗？谁在起作用？

* **实质**：Agent 根本不知道有几个 Server。起作用的是 **Cursor（宿主客户端）的大管家路由功能**。
* **机制**：Cursor 读取 `mcp.json` 连上所有 Server，把所有工具融合成一个超级列表发给 Agent。Agent 决定调用某个工具时，Cursor 会查内部映射表，精准地把请求路由到对应的那个 Python 进程。

### 6. `async with httpx.AsyncClient() as client:` 语法解析

* 这是纯 Python 的现代异步并发语法。`async with` 负责安全地“开门和关门”（管理连接资源）。`await client.get()` 表示异步 I/O：在等待网络请求结果的几秒钟里，不阻塞 Python 进程处理其他事务。

---

## 三、 实战项目一：arXiv 论文搜索 (基础 Tool + Stdio)

* **架构目的**：验证最核心的 `Agent -> MCP (Stdio) -> Python -> HTTP API` 链路。
* **工程决策**：放弃了需要繁琐鉴权的 GitLab，选择数据结构清晰、无需 Token 且返回古老 XML 的 arXiv，完美展示了 MCP Server 作为“翻译官”（XML 转 JSON-RPC 纯文本）的价值。
* **踩坑与解决**：
* **现象**：Inspector 找不到输入框。**原因**：错把 Tool 当成了 Resource 页面。
* **报错**：`301 Moved Permanently`。**原因**：httpx 库极其严谨，不会默认跟随 HTTP 到 HTTPS 的重定向。**解决**：将代码中的 URL 从 `http://` 改为 `https://`。



---

## 四、 实战项目二：Kitchen Assistant (三大抽象融合 + 状态读写)

* **架构目的**：在一个项目中同时实现 Resource (读)、Tool (读/写) 和 Prompt，展示处理有副作用（Mutating State）业务的进阶能力。
* **工作流逻辑设计（Agentic Workflow）**：
1. **被动档案**：将本地的 `preferences.json` 挂载为 Resource。
2. **读写拆分**：定义 `update_preferences` (Tool，写操作) 和 `look_into_fridge` (Tool，读操作，拉取图片激活多模态)。
3. **架构降维**：为了解决“请执行 plan_dinner prompt”过于生硬的问题，我们将 Prompt 模板删除，把 SOP 指令直接写入 `check_preferences` 工具的注释说明中。
4. **智能体自驱执行**：当输入“我饿了”，Agent 发现必须先调用偏好工具 -> 发现没有偏好 -> 触发分支逻辑主动询问用户 -> 调用工具记录偏好 -> 调用工具看冰箱 -> 出菜谱。


* **踩坑与解决**：
* **报错**：`ImportError` 找不到 `Message`。**原因**：SDK 版本迭代。**解决**：FastMCP 支持极简模式，直接返回多行 `str` 即可。
* **报错**：`429 Too Many Requests`。**原因**：GitHub 对自动化程序抓取 Web 前端（带有 `/blob/`）限流极严。**解决**：手动拼接提取 `raw.githubusercontent.com` 的纯净 CDN 链接，并在请求中添加标准的 `User-Agent` Headers。



---

## 五、 实战项目三：Kitchen Remote (云原生微服务 + SSE 协议)

* **架构目的**：打破本地 `Stdio` 进程通信的束缚，部署工业级的分布式网络服务。
* **核心重构**：
1. 引入 `starlette` 和 `uvicorn`。
2. 将 `mcp.run()` 修改为 `mcp.run(transport="sse")`。
3. Cursor 配置由执行本地 `command` 变更为网络端点 `"type": "sse", "url": "http://localhost:8000/sse"`。


* **云端存储理念**：在真实的云端（Render, AWS），本地磁盘是易失的，图片应继续留在 CDN，而 `preferences.json` 必须剥离，重构为真实的云端数据库（如 PostgreSQL 或 Key-Value Store）。

> **我的综合理解与纠偏总结：**
> “我的理解是这样的：我们假装 port 8000 在远端（实际可部署在真实服务器上开放端口）。MCP 自定义脚本被运行并开放端口等待交流。Cursor 扫描 MCP 服务，通过 SSE 连接到远端端口。当我提出需求，Agent 找到功能，便把打包好的 JSON-RPC 信息传给远端的 MCP Server。Server 执行查询偏好等操作后，返回信息给 Agent，Agent 整合给用户。这样 MCP 代码本身和 Python 运行环境都可以放得很远，剥离出本地。”
> **底层通信纠偏**：SSE (Server-Sent Events) 本质是**“单向流式通道”**。Agent 真正的请求（如“我饿了”触发的调用）是通过 **HTTP POST** 发送的，而远端 Server 计算完毕后，是顺着那条一直保持连接的 **SSE 通道** 把结果推回给 Agent。这被称为 HTTP with SSE Transport。
