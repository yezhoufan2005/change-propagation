<script lang="ts" setup>
import { BottomPart, DataCard, MessageLevelPie, MessageShareCard, TopChart } from './components'
</script>

<template>
  <NSpace :vertical="true" :size="16">
    <TopChart />
    <DataCard />
    <MessageShareCard />
    <MessageLevelPie />
    <BottomPart />
  </NSpace>
</template>

<style scoped></style>
