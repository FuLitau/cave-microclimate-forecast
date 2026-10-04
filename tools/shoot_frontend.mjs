/**
 * 前端目视核验工具：用 CDP 驱动无头 Chrome 逐路由截图，同时抓取控制台报错与 404。
 *
 * 为什么需要它：`npm run build` 通过只说明能打包，不代表运行时能渲染。
 * 之前的 `/compare` 路由就能构建成功、打开却整页空白 —— 只有真实浏览器能发现。
 *
 * 用法（需先把产物用静态服务器托管，例如
 *   python -m http.server 4173 --directory frontend/dist）：
 *   node tools/shoot_frontend.mjs --base http://127.0.0.1:4173 --out _shots
 *
 * 参数：
 *   --base   站点根地址（默认 http://127.0.0.1:4173）
 *   --out    截图输出目录（默认 _shots）
 *   --width  视口宽度（默认 1600）
 *   --height 初始视口高度（默认 1200）；若主内容区更高会自动加高后重截
 *   --routes 逗号分隔的路由（默认 /,/compare,/validation,/method）
 *   --port   DevTools 调试端口（默认 9333）
 *   --chrome Chrome 可执行文件路径
 *
 * 退出码：任何路由出现未捕获异常、控制台 error 或非 favicon 的 4xx/5xx 即为 1。
 */
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join, resolve } from 'node:path'

const argv = process.argv.slice(2)
const opt = (name, def) => {
  const i = argv.indexOf('--' + name)
  return i >= 0 && argv[i + 1] ? argv[i + 1] : def
}

const BASE = opt('base', 'http://127.0.0.1:4173').replace(/\/$/, '')
const OUT = resolve(opt('out', '_shots'))
const WIDTH = Number(opt('width', '1600'))
const HEIGHT = Number(opt('height', '1200'))
const PORT = Number(opt('port', '9333'))
// 路由是 hash 模式（见 frontend/src/router.ts），除首页外都必须写成 /#/xxx，
// 否则静态服务器会把 /compare 当成真实路径返回 404。
const ROUTES = opt('routes', '/,/#/compare,/#/validation,/#/method').split(',').map((s) => s.trim()).filter(Boolean)
const CHROME = opt('chrome', 'C:/Program Files/Google/Chrome/Application/chrome.exe')
const PROFILE = join(OUT, '_chrome_profile')

mkdirSync(OUT, { recursive: true })

const nameOf = (route) => {
  const clean = route.replace(/#/g, '/')
  return clean === '/' || clean === '' ? 'console' : clean.replace(/^\/+|\/+$/g, '').replace(/\W+/g, '_')
}
const IGNORABLE = /favicon\.ico$/i

class CDP {
  constructor(url) {
    this.ws = new WebSocket(url)
    this.seq = 0
    this.pending = new Map()
    this.events = []
    this.ready = new Promise((ok, bad) => {
      this.ws.addEventListener('open', () => ok())
      this.ws.addEventListener('error', (e) => bad(new Error('ws error: ' + (e.message ?? 'unknown'))))
    })
    this.ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id != null && this.pending.has(msg.id)) {
        const { ok, bad } = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        msg.error ? bad(new Error(msg.error.message)) : ok(msg.result)
      } else if (msg.method) {
        this.events.push(msg)
      }
    })
  }
  send(method, params = {}, sessionId) {
    const id = ++this.seq
    const payload = { id, method, params }
    if (sessionId) payload.sessionId = sessionId
    return new Promise((ok, bad) => {
      this.pending.set(id, { ok, bad })
      this.ws.send(JSON.stringify(payload))
    })
  }
  drainEvents() {
    const out = this.events
    this.events = []
    return out
  }
  close() {
    try { this.ws.close() } catch { /* ignore */ }
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function waitForDevtools() {
  for (let i = 0; i < 120; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`)
      if (r.ok) return await r.json()
    } catch { /* not up yet */ }
    await sleep(200)
  }
  throw new Error(`DevTools 在 ${PORT} 端口不可达，请检查 Chrome 路径与端口占用`)
}

/** 从 CDP 事件流里提取控制台报错、未捕获异常与真实 404（favicon 除外） */
function collectProblems(events) {
  const problems = []
  const statusOf = new Map()
  for (const e of events) {
    if (e.method === 'Network.responseReceived') {
      const { url, status } = e.params.response
      if (status >= 400) statusOf.set(url, status)
    }
  }
  for (const [url, status] of statusOf) {
    if (!IGNORABLE.test(url)) problems.push(`HTTP ${status}: ${url}`)
  }
  for (const e of events) {
    if (e.method === 'Runtime.exceptionThrown') {
      const d = e.params.exceptionDetails
      const desc = d.exception?.description ?? d.text ?? 'unknown'
      problems.push(`未捕获异常: ${desc.split('\n').slice(0, 5).join(' | ')}`)
    } else if (e.method === 'Runtime.consoleAPICalled' && (e.params.type === 'error' || e.params.type === 'warning')) {
      const text = e.params.args.map((a) => a.value ?? a.description ?? a.type).join(' ')
      problems.push(`console.${e.params.type}: ${text.slice(0, 260)}`)
    } else if (e.method === 'Log.entryAdded' && e.params.entry.level === 'error') {
      // 资源加载失败已由 Network 域单独汇报，这里跳过以免重复
      if (!/Failed to load resource/i.test(e.params.entry.text)) {
        problems.push(`log: ${e.params.entry.text}`.slice(0, 260))
      }
    }
  }
  return [...new Set(problems)]
}

const chrome = spawn(
  CHROME,
  [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--hide-scrollbars',
    '--force-device-scale-factor=1',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    'about:blank',
  ],
  { stdio: 'ignore' },
)

let failed = 0
try {
  // 浏览器级 WebSocket 端点必须用 /json/version 返回的完整 URL（带 UUID），
  // 自己拼 /devtools/browser 会被 Chrome 以非 101 状态拒绝。
  const info = await waitForDevtools()
  const cdp = new CDP(info.webSocketDebuggerUrl)
  await cdp.ready

  for (const route of ROUTES) {
    const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' })
    const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true })
    cdp.drainEvents()

    await cdp.send('Page.enable', {}, sessionId)
    await cdp.send('Runtime.enable', {}, sessionId)
    await cdp.send('Network.enable', {}, sessionId)
    await cdp.send('Log.enable', {}, sessionId)
    const setViewport = (height) =>
      cdp.send('Emulation.setDeviceMetricsOverride',
        { width: WIDTH, height, deviceScaleFactor: 1, mobile: false }, sessionId)

    await setViewport(HEIGHT)
    await cdp.send('Page.navigate', { url: BASE + route }, sessionId)
    await sleep(3500) // 给 ECharts 画布与字体留出渲染时间

    // 本应用是固定 100vh 的外壳 + 主内容区内部滚动，所以文档高度恒等于视口高度。
    // 要截全页，必须按主内容区的 scrollHeight 把视口撑高后再截。
    const probe = await cdp.send('Runtime.evaluate', {
      expression: `(() => { const m = document.querySelector('.main');
        const h = m ? m.scrollHeight : document.documentElement.scrollHeight;
        const tb = document.querySelector('.topbar');
        return Math.ceil(h + (tb ? tb.getBoundingClientRect().height : 0) + 8); })()`,
      returnByValue: true,
    }, sessionId)
    const wanted = Math.min(Number(probe.result.value) || HEIGHT, 24000)
    if (wanted > HEIGHT + 20) {
      await setViewport(wanted)
      await sleep(900)
    }

    const shot = await cdp.send('Page.captureScreenshot', { format: 'png' }, sessionId)
    writeFileSync(join(OUT, nameOf(route) + '.png'), Buffer.from(shot.data, 'base64'))

    const problems = collectProblems(cdp.drainEvents())
    if (problems.length) failed++
    console.log(`${problems.length ? 'FAIL' : 'OK  '} ${route.padEnd(14)} 视口高 ${String(Math.max(wanted, HEIGHT)).padStart(5)}px -> ${nameOf(route)}.png`)
    for (const p of problems) console.log('       ! ' + p)

    await cdp.send('Target.closeTarget', { targetId })
  }
  cdp.close()
} finally {
  try { chrome.kill() } catch { /* ignore */ }
  await sleep(600)
  try { rmSync(PROFILE, { recursive: true, force: true }) } catch { /* Chrome 可能仍持有文件锁 */ }
}

console.log(failed ? `\n共 ${failed} 个路由存在运行时问题` : '\n全部路由无控制台报错')
process.exit(failed ? 1 : 0)
