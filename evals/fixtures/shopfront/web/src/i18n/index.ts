import zh from './zh.json'
import en from './en.json'

const dictionaries: Record<string, Record<string, string>> = { zh, en }
let locale = 'zh'

export function setLocale(next: 'zh' | 'en') {
  locale = next
}

export function t(key: string): string {
  return dictionaries[locale][key] ?? key
}
