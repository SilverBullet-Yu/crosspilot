<script setup lang="ts">
/**
 * 应用外壳 —— 左侧工作台导航 + 顶栏（面包屑 / 演示模式徽标 / 用户）。
 * 三页共用（产品概览 / 卖点验证工作台 / 历史验证项目）。
 * 插槽：#default 页面主区；#sidebar 页面级侧栏扩展（工作台页放「本次验证」导航与数据源 meta）。
 * 图标为内联 SVG 手绘（依赖最小化约束：不引入图标库）；侧栏可折叠为图标栏。
 */
const route = useRoute()

defineProps<{ /** 顶栏面包屑当前页名 */ crumb: string }>()

const NAV = [
  { path: "/", label: "产品概览", icon: "home" },
  { path: "/workbench", label: "卖点验证工作台", icon: "grid" },
  { path: "/history", label: "历史验证项目", icon: "clock" },
] as const

const collapsed = ref(false)
const isActive = (path: string) => route.path === path
</script>

<template>
  <div class="shell" :class="{ 'shell--collapsed': collapsed }">
    <aside class="sidebar">
      <NuxtLink to="/" class="side__logo" aria-label="CrossPilot 2.0 产品概览">
        <svg class="side__logomark" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10" fill="var(--accent)" />
          <path d="M15.8 8.2 10.6 10.6 8.2 15.8 13.4 13.4Z" fill="#fff" />
        </svg>
        <span class="side__logotext">CrossPilot</span>
        <span class="side__logo-ver">2.0</span>
      </NuxtLink>

      <div class="side__workspace">
        <span class="side__wsavatar" aria-hidden="true">跨</span>
        <div class="side__wstext">
          <p class="side__wsname">我的品牌空间</p>
          <p class="side__wssub">个人工作空间</p>
        </div>
        <button
          type="button"
          class="side__collapse"
          :title="collapsed ? '展开侧栏' : '收起侧栏'"
          :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
          @click="collapsed = !collapsed"
        >
          <svg class="side__collapseicon" :class="{ 'side__collapseicon--flip': collapsed }" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" stroke-width="1.5" />
          </svg>
        </button>
      </div>

      <p class="side__label">工作空间</p>
      <nav class="side__nav" aria-label="主导航">
        <NuxtLink
          v-for="n in NAV"
          :key="n.path"
          :to="n.path"
          class="side__navitem"
          :class="{ 'side__navitem--active': isActive(n.path) }"
        >
          <svg v-if="n.icon === 'home'" class="side__navicon" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M2.5 7.5 8 2.8l5.5 4.7V13a.9.9 0 0 1-.9.9h-2.7v-3.4H6.1v3.4H3.4a.9.9 0 0 1-.9-.9Z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" />
          </svg>
          <svg v-else-if="n.icon === 'grid'" class="side__navicon" viewBox="0 0 16 16" aria-hidden="true">
            <g fill="none" stroke="currentColor" stroke-width="1.3">
              <rect x="2.5" y="2.5" width="4.6" height="4.6" rx="1" />
              <rect x="8.9" y="2.5" width="4.6" height="4.6" rx="1" />
              <rect x="2.5" y="8.9" width="4.6" height="4.6" rx="1" />
              <rect x="8.9" y="8.9" width="4.6" height="4.6" rx="1" />
            </g>
          </svg>
          <svg v-else class="side__navicon" viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="8" cy="8" r="5.7" fill="none" stroke="currentColor" stroke-width="1.3" />
            <path d="M8 4.8V8l2.2 1.4" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
          </svg>
          <span class="side__navtext">{{ n.label }}</span>
          <svg v-if="isActive(n.path)" class="side__navchev" viewBox="0 0 16 16" aria-hidden="true">
            <path d="m6 4 4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.4" />
          </svg>
        </NuxtLink>
      </nav>

      <div class="side__slot">
        <slot name="sidebar" />
      </div>
      <div class="side__spacer"></div>

      <div v-if="route.path !== '/workbench'" class="side__lab">
        <svg class="side__labicon" viewBox="0 0 16 16" aria-hidden="true">
          <path d="M6.5 2.5h3M7 2.5v4L3.6 12a1.6 1.6 0 0 0 1.4 2.4h6a1.6 1.6 0 0 0 1.4-2.4L9 6.5v-4" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" />
        </svg>
        <p class="side__labtitle">让判断，回到证据。</p>
        <p class="side__labbody">从一个卖点假设开始，找到值得验证的下一个问题。</p>
        <NuxtLink to="/workbench" class="side__lablink">体验演示工作台 ↗</NuxtLink>
      </div>

      <div class="side__version">
        <span class="side__versiondot" aria-hidden="true"></span>
        <span class="side__versiontext">极客松演示版本</span>
        <span class="side__mvp">MVP</span>
      </div>
    </aside>

    <div class="shell__main">
      <header class="topbar">
        <nav class="crumbs" aria-label="面包屑">
          <NuxtLink to="/" class="crumbs__root">工作空间</NuxtLink>
          <svg class="crumbs__chev" viewBox="0 0 16 16" aria-hidden="true">
            <path d="m6 4 4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.4" />
          </svg>
          <span class="crumbs__page">{{ crumb }}</span>
        </nav>
        <div class="topbar__right">
          <span class="modechip"><span class="modechip__dot" aria-hidden="true"></span>演示模式 · Mock 数据</span>
          <span class="topbar__user" title="演示用户">我</span>
        </div>
      </header>
      <main class="appmain">
        <slot />
      </main>
    </div>
  </div>
</template>
