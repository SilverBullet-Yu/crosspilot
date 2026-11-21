// Nuxt 配置 —— CrossPilot 2.0 三栏证据对照界面
// 数据来源由环境变量 NUXT_PUBLIC_API_BASE 决定（自动注入 runtimeConfig.public.apiBase）：
//   - 取值为空或 "fixtures" → 读 apps/web/fixtures/ 本地夹具（三个场景各一份，后端不可用时仍可演示）
//   - 取值为 URL（如 http://localhost:8000）→ 调真实 FastAPI：GET /api/evidence 与 /api/evidence/demo
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  // 手写全局 CSS：不引入任何 UI 组件库（依赖最小化约束）
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    public: {
      // 默认走本地 fixtures；接入真实 API 时设 NUXT_PUBLIC_API_BASE=http://localhost:8000
      apiBase: 'fixtures',
    },
  },
})
