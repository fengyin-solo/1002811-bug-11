<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <div class="stat-row" v-if="plotSummary">
      <article class="stat-card">
        <span class="stat-label">待接管绿地</span>
        <strong class="stat-value">{{ plotSummary['待接管'] }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已接管绿地</span>
        <strong class="stat-value">{{ plotSummary['已接管'] }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已移交绿地</span>
        <strong class="stat-value">{{ plotSummary['已移交'] }}</strong>
      </article>
      <article class="stat-card highlight">
        <span class="stat-label">在管面积（㎡，按接管明细重算）</span>
        <strong class="stat-value">{{ formatArea(plotSummary['在管面积']) }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type PlotSummary = {
  待接管: number
  已接管: number
  已移交: number
  在管面积: number
}

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
  plotSummary?: PlotSummary
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const plotSummary = ref<PlotSummary | null>(null)

function formatArea(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
    plotSummary.value = payload.plotSummary ?? null
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "绿地台账", "created": 0, "pending": 0, "abnormal": 0}, {"name": "乔木管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "灌木管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "草坪管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "花卉造景", "created": 0, "pending": 0, "abnormal": 0}, {"name": "病虫害防治", "created": 0, "pending": 0, "abnormal": 0}, {"name": "灌溉作业", "created": 0, "pending": 0, "abnormal": 0}, {"name": "施肥作业", "created": 0, "pending": 0, "abnormal": 0}, {"name": "修剪造型", "created": 0, "pending": 0, "abnormal": 0}, {"name": "绿地巡查", "created": 0, "pending": 0, "abnormal": 0}, {"name": "杂草清除", "created": 0, "pending": 0, "abnormal": 0}, {"name": "树木支撑", "created": 0, "pending": 0, "abnormal": 0}, {"name": "苗木移植", "created": 0, "pending": 0, "abnormal": 0}, {"name": "园建设施", "created": 0, "pending": 0, "abnormal": 0}, {"name": "园林机械", "created": 0, "pending": 0, "abnormal": 0}, {"name": "苗木基地", "created": 0, "pending": 0, "abnormal": 0}, {"name": "水体养护", "created": 0, "pending": 0, "abnormal": 0}, {"name": "名木古树", "created": 0, "pending": 0, "abnormal": 0}, {"name": "市民热线", "created": 0, "pending": 0, "abnormal": 0}, {"name": "季度养护方案", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>

<style scoped>
.stat-card.highlight { border-color: #1f6feb; background: #f0f6ff; }
</style>
