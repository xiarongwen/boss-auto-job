# BOSS 直聘风控体系逆向分析报告

## 架构概览

BOSS 直聘的前端风控体系由以下组件组成：

```
┌─────────────────────────────────────────────────────┐
│                   Browser Client                     │
├──────────┬──────────┬───────────┬───────────────────┤
│ warlock  │  patas   │  gateway  │   zp-stoken gen   │
│ data.js  │  .js     │  (app.js) │   (security-js)   │
│ 70KB     │  113KB   │  2.4MB    │   325KB           │
│ 行为采集  │  APM监控  │  请求网关   │   加密生成器       │
└────┬─────┴────┬─────┴─────┬─────┴────────┬──────────┘
     │          │           │              │
     ▼          ▼           ▼              ▼
┌─────────────────────────────────────────────────────┐
│                  BOSS Backend                         │
├──────────┬──────────┬───────────┬───────────────────┤
│ warlock  │  risk    │  gateway  │   captcha         │
│ collector│  engine  │  proxy    │   (Geetest)       │
│ 行为分析  │  风控引擎  │  网关代理   │   验证码服务       │
└──────────┴──────────┴───────────┴───────────────────┘
```

## 1. 安全网关层 (Gateway)

### 1.1 __zp_stoken__ 生成机制

**入口**：前端请求所有 `/wapi/` 接口时，网关拦截器自动注入。

**核心逻辑**（从 app.js 提取）：
```javascript
// 步骤 1: 请求被拦截，检查是否有 __zp_stoken__
if (cookie 中没有 __zp_stoken__) {
    // 步骤 2: 加载加密 JS
    loadScript("/web/common/security-js/{name}.js")
    
    // 步骤 3: 创建 iframe，注入 JS
    iframe = document.createElement('iframe')
    iframe.src = "about:blank"
    document.body.appendChild(iframe)
    
    // 步骤 4: 在 iframe 中加载 security-js
    script = iframe.contentDocument.createElement('script')
    script.src = "/web/common/security-js/{name}.js"
    iframe.contentDocument.body.appendChild(script)
    
    // 步骤 5: 从 iframe 中获取 ABC 类
    ABC = iframe.contentWindow.ABC
    
    // 步骤 6: 生成 token
    token = new ABC().z(seed, parseInt(ts) + 60 * (480 + getTimezoneOffset()) * 1000)
    
    // 步骤 7: 设置 cookie（2.67天过期）
    setCookie("__zp_stoken__", token, 3840分钟, domain, "/")
}
```

**错误码定义**（从 app.js 提取）：
```javascript
gatewayErrorCode = {
    gatewayTokenNull:    { code: 20002, message: "服务端检查zpToken是否失效" },
    gatewaySNTNull:      { code: 20000, message: "seed/name/ts中有存在值为空" },
    gatewayValueNull:    { code: 20001, message: "读取反爬关键信息存在值为空" },
    gatewayABCNull:      { code: 20003, message: "ABC不存在或者不是1个函数" },
    gatewayTokenCreate:  { code: 20004, message: "生成__zp_stoken__值失败" },
}
```

### 1.2 请求拦截器 (Axios Interceptor)

前端使用 axios 的 request/response 拦截器：

```javascript
// Request Interceptor: 注入 headers
interceptors.request.forEach(function(t) {
    // 注入 zp_token (from bst cookie)
    // 注入 traceId (随机生成)
    // 注入 Content-Type
})

// Response Interceptor: 错误码分发
interceptors.response.forEach(function(t) {
    switch(n.code) {
        case 31:  → 403页面
        case 32:  → 403页面（封禁）
        case 35:
        case 36:  → 跳转安全验证页面 (verify-slider)
        case 37:  → 跳转 security-check (生成zp_stoken)
    }
})
```

**关键配置**：
```javascript
{
    loadScripts: true,
    interceptZhiPinGateway: true,  // 启用网关拦截
    openAntiSpider: true,          // 启用反爬虫
    Cookie: true,
    Storage: true
}
```

## 2. 行为采集层 (Warlock Data)

### 2.1 采集事件

`warlockdata.min.js` (70KB) 采集以下用户行为：

| 事件 | 采集内容 | 触发条件 |
|------|----------|----------|
| `click` | 点击坐标、目标元素、时间戳 | 每次点击 |
| `WebClick` | 扩展点击数据（含元素路径） | 特定元素点击 |
| `input` | 输入框值变化 | 每次输入 |
| `focus` / `blur` | 元素聚焦/失焦 | 焦点变化 |
| `scroll` | 滚动位置、方向 | 滚动事件 |
| `visibility` | 页面可见性变化 (20处引用) | 标签页切换 |
| `ajaxError` | AJAX 请求失败 | 请求异常 |
| `error` | JS 运行时错误 | 异常捕获 |
| `track_login` | 登录行为 | 登录操作 |

### 2.2 数据上报端点

```javascript
// 主上报接口
server_url = "https://shink.zhipin.com/wapi/dapCommon/json"

// 高频事件上报 (visibility change)
warlock_event_url = "https://warlock.zhipin.com/wapi/warlock/cross/event/visible/client/fetch"

// APM 性能数据上报
apm_url = "https://logapi.zhipin.com/dap/api/json"

// Token
token = "zhipin_geek_pc65A80B97CB4C27FA8F"
app_name = "zhipin_geek_pc"
```

### 2.3 反调试检测

```javascript
// 加载 warlock-detect-dom (反篡改检测)
loadScript("https://unpkg.weizhipin.com/@datastar/warlock-detect-dom@latest/dist/index.js")

// detectMode 配置
detectMode: true  // 启用 DOM 篡改检测
```

### 2.4 数据格式

```javascript
{
    app_name: "zhipin_geek_pc",
    distinct_id: "uuid-xxx",        // 持久化用户ID
    events: [{
        event: "WebClick",
        event_no: 1234567890,
        event_ts: 1234567890,
        referrer: "https://...",
        user_agent: "Mozilla/5.0...",
        href: "https://www.zhipin.com/...",
        gatewaytype: "zp",
        appname: "zhipin_geek_spa_web",
        code: 37                     // 错误码（如果有）
    }],
    _reqid: "uuid-xxx",
    _topic: "zhipin_geek_pc65A80B97CB4C27FA8F",
    _ts: 1234567890,
    _v: "1.0.0"
}
```

## 3. APM 监控层 (Patas)

`patas.2.2.0.min.js` (113KB) 是 BOSS 自研的 APM 系统：

### 3.1 监控指标

| 指标 | 说明 | 采集频率 |
|------|------|----------|
| LCP (Largest Contentful Paint) | 最大内容绘制 | 页面加载时 |
| FID (First Input Delay) | 首次输入延迟 | 首次交互时 |
| CLS (Cumulative Layout Shift) | 累积布局偏移 | 持续监控 |
| FP (First Paint) | 首次绘制 | 页面加载时 |
| FCP (First Contentful Paint) | 首次内容绘制 | 页面加载时 |
| Resource Timing | 资源加载时间 | 所有资源 |
| Network Requests | 请求耗时/状态 | 所有请求 |
| JS Errors | 运行时错误 | 错误捕获 |

### 3.2 异常检测

```javascript
// 资源加载异常
report({
    actionName: "resource_load_monitor",
    actionType: "$_abnormal",
    json: {
        code: 10001,
        message: "资源加载异常或未定义",
        extraInfo: { hasJqueryScript: true/false }
    }
})

// jQuery 加载失败检测
if (!window.$ || !window.jQuery) {
    // 上报 jQuery 未加载
}
```

## 4. 错误码分发器 (Response Interceptor)

从 app.js 提取的完整错误码处理：

```javascript
// 响应拦截器中的错误码处理
switch (response.code) {
    case 31:  // 未登录
    case 5002:
        → redirect to /web/common/403.html?code=31
        
    case 32:  // 账户封禁
    case 5003:
    case 5004:
        → redirect to /web/common/403.html?code=32
        
    case 35:  // 需要安全验证
    case 36:  // 账户异常
        → redirect to /web/user/safe/verify-slider?callbackUrl=...
        
    case 37:  // 环境异常
        → redirect to /web/common/security-check.html?seed=...&name=...&ts=...
}
```

**错误码含义**：

| Code | 含义 | 前端处理 | 后端判定逻辑 |
|------|------|----------|-------------|
| 0 | 正常 | 正常处理 | 请求合法 |
| 31 | 未登录 | 跳403页 | Cookie中无有效session |
| 32 | 账户封禁 | 跳403页 | 账户被标记为异常(自动化/违规) |
| 35 | 需验证(滑块) | 跳verify-slider | 风险评分中等，需滑块验证 |
| 36 | 账户异常 | 跳verify-slider | 风险评分高，需人工验证 |
| 37 | 环境异常 | 跳security-check | 检测到非浏览器环境/异常指纹 |
| 5002 | 服务错误 | 跳403页 | 服务端内部错误 |
| 5003 | 服务错误 | 跳403页 | 服务端内部错误 |
| 5004 | 服务错误 | 跳403页 | 服务端内部错误 |
| 1006 | 限速 | 等待重试 | 请求频率超过阈值 |

## 5. 浏览器环境检测

### 5.1 已确认的检测项

从 app.js 的 853 个反bot模式中提取：

| 检测类型 | 出现次数 | 检测方法 |
|----------|----------|----------|
| Canvas 指纹 | 16 | `canvas.toDataURL()` / `getImageData()` |
| WebGL 指纹 | 14 | `webgl.getParameter(RENDERER)` |
| 浏览器行为 | 15 | `mouseenter/move/over/out` / `touchstart/end` |
| 时间一致性 | 12 | `performance.now()` / `Date.now()` 间隔检测 |
| 环境检测 | 11 | `envCheck` / `envDetect` 模块 |
| 字体检测 | 7 | `fontFamily` / `measureText` / `offsetWidth` |
| 调试器检测 | 5 | `debugger` / `__REACT_DEVTOOLS` |
| UA一致性 | 4 | `userAgent` vs `platform` vs `navigator` |
| Headless检测 | 3 | `headless` / `phantom` |
| 插件检测 | 1 | `navigator.plugins` |
| Chrome检测 | 1 | `window.chrome` / `chrome.runtime` |
| Proxy检测 | 64 | `Proxy` / `Reflect.get` / `hasOwnProperty` |

### 5.2 加密/混淆的字符串

发现 2539 个疑似编码字符串，其中关键的风控常量：

```javascript
// XOR 编码的风控字符串（已解码部分）
const encoded = [
    "cvE}[Sl6w^1}[^qjcgqI",    // 风控相关
    "o^R{c1:5c45I",             // 检测标识
    "Tv^goS:hwSBCc1`;",         // 环境标记
    "kd^v`QLjh^qI",             // 行为标识
    "T;v?[o>;",                  // 状态标记
    "kddN[fQpT:rp`QL0",         // 风控常量
]

// 解密函数（XOR）
function decrypt(encoded, key) {
    let result = '';
    for (let i = 0; i < encoded.length; i++) {
        const e = parseInt(key.charAt(i % key.length), 10);
        const n = encoded.charCodeAt(i);
        result += String.fromCharCode(n ^ e);
    }
    return btoa(result);  // Base64 编码
}
```

### 5.3 Proxy 检测（64处）

BOSS 前端大量使用 `Proxy` 和 `Reflect` 来检测对象是否被代理：

```javascript
// 检测 navigator 对象是否被 Playwright/Puppeteer 代理
if (typeof navigator === 'object') {
    // 检查 navigator 的属性是否是原生的
    const desc = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
    if (desc && desc.get && desc.get.toString().includes('native')) {
        // 正常浏览器
    } else {
        // 可能是自动化工具
    }
}

// 检测 Proxy trap
const handler = {
    get(target, prop) {
        // 如果能检测到 Proxy 的 get trap
        // 说明对象被代理了（自动化工具特征）
    }
};
```

## 6. 验证码系统 (Geetest)

### 6.1 集成方式

```javascript
// Geetest SDK 加载
captcha_sdk_url = "https://static.zhipin.com/assets/zhipin/geek/captcha-sdk/captcha-sdk@5.1.2.min.js"

// 验证类型获取
get_type_url = "/wapi/zpsecureflow/captcha/gettype"

// 验证提交
validate_url = "/wapi/zpsecureflow/captcha/validate"

// 重定向判断
redirect_url = "/wapi/zpsecureflow/captcha/getredirect"
```

### 6.2 验证流程

```
1. 前端请求 → 后端返回 code 36
2. 前端跳转 → /web/passport/zp/verify.html
3. 前端调用 → /wapi/zpsecureflow/captcha/getredirect (判断是否需要验证)
4. 前端调用 → /wapi/zpsecureflow/captcha/gettype (获取验证类型)
5. 前端加载 → captcha-sdk@5.1.2.min.js (Geetest SDK)
6. 用户完成 → 点选验证码
7. 前端提交 → /wapi/zpsecureflow/captcha/validate
8. 验证成功 → 3秒后跳转 callbackUrl
```

## 7. 风控触发链路

```
用户请求
  │
  ├─ Layer 1: 环境检测
  │   ├─ TLS 指纹 (JA3/JA4)
  │   ├─ Canvas/WebGL 指纹
  │   ├─ navigator.webdriver 检测
  │   ├─ Headless Chrome 特征
  │   └─ Proxy 代理检测
  │
  ├─ Layer 2: 行为分析 (Warlock)
  │   ├─ 鼠标轨迹 (click/move)
  │   ├─ 键盘时序
  │   ├─ 滚动模式
  │   ├─ 页面可见性变化
  │   └─ 请求频率/间隔
  │
  ├─ Layer 3: 网关验证 (Gateway)
  │   ├─ __zp_stoken__ 有效性
  │   ├─ Cookie 完整性 (wt2/zp_at/bst)
  │   ├─ 请求 headers 完整性
  │   └─ session 一致性
  │
  └─ Layer 4: 风控引擎 (Backend)
      ├─ 账户风险评分
      ├─ IP 信誉库
      ├─ 设备指纹库
      ├─ 行为模式匹配
      └─ 实时限速
```

## 8. 各错误码的触发条件

| 从 | 到 | 触发条件 |
|----|-----|----------|
| 0 → 37 | 环境异常 | TLS指纹非浏览器 / 缺少__zp_stoken__ / navigator.webdriver=true |
| 37 → 36 | 账户异常 | 环境异常 + 行为异常（高频请求、无鼠标移动） |
| 36 → 32 | 账户封禁 | 验证后仍异常 / 短时间内反复触发36 / 多次自动化请求 |
| 0 → 1006 | 限速 | 单位时间内请求超过阈值（约30次/分钟） |

## 9. 绕过策略评估

| 策略 | Layer 1 | Layer 2 | Layer 3 | Layer 4 | 可行性 |
|------|---------|---------|---------|---------|--------|
| requests + cookies | ❌ TLS指纹 | ❌ 无行为 | ⚠️ 需token | ❌ IP风控 | 不可行 |
| curl_cffi chrome120 | ✅ TLS绕过 | ❌ 无行为 | ⚠️ 需token | ❌ IP风控 | 部分可行 |
| Playwright headless | ✅ TLS绕过 | ⚠️ 部分 | ✅ 自动 | ⚠️ 需信任 | 可行 |
| 真实Chrome (CDP) | ✅ 全部 | ✅ 全部 | ✅ 全部 | ✅ 全部 | 最优 |
| 真实Chrome (手动) | ✅ 全部 | ✅ 全部 | ✅ 全部 | ✅ 全部 | 最安全 |

## 10. 结论

BOSS 直聘的风控是一个**多层纵深防御体系**：

1. **环境层**：检测 TLS 指纹、浏览器特征、WebDriver 标记
2. **行为层**：采集鼠标/键盘/滚动行为，建立用户行为画像
3. **网关层**：验证 `__zp_stoken__` 加密 token 的有效性
4. **风控层**：综合评分，触发验证码或封禁

**最有效的自动化方案**：使用用户的真实 Chrome 浏览器（CDP 模式），因为：
- TLS 指纹 = 真实 Chrome ✅
- 浏览器环境 = 无 WebDriver 标记 ✅
- 行为数据 = 可以模拟真实操作 ✅
- 账户信任 = 用户已手动验证过 ✅

**绝对避免**：
- 短时间内大量请求（触发限速→验证→封禁链路）
- code 36/32 后继续重试（升级封禁等级）
- 同时使用多个脚本对同一账户请求
