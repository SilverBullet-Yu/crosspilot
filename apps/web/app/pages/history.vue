<script setup lang="ts">
/**
 * 历史验证项目 —— 验证运行记录页。
 * 演示构建（fixtures 模式）不做持久化，验证在工作台即时完成；
 * 本页如实呈现空态，不虚构历史数据。
 */
useHead({ title: "历史验证项目 · CrossPilot 2.0" })
</script>

<template>
  <AppShell crumb="历史验证项目">
    <div class="history">
      <section class="history__panel">
        <h1 class="history__title">暂无历史验证项目</h1>
        <p class="history__body">
          演示构建不做持久化——每次验证在卖点验证工作台即时完成，不落库存档。
          发起一次验证后，判定与建议动作的留痕可在工作台中直接查看。
        </p>
        <NuxtLink to="/workbench" class="btn btn--primary">去发起一次验证 →</NuxtLink>
      </section>
    </div>
  </AppShell>
</template>
