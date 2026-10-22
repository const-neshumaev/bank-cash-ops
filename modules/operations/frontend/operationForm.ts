import type {
  Currency,
  SlotDef,
  WorkplaceContext,
  WorkplaceOperation,
  WorkplaceRate,
} from './api/operations'

export interface ExchangeSlots {
  basis: SlotDef
  computed: SlotDef
  rate: SlotDef
}

export function exchangeSlots(operation: WorkplaceOperation): ExchangeSlots | null {
  const computed = operation.slots.find((slot) => slot.amount_mode === 'computed')
  const rate = operation.slots.find((slot) => slot.stores_rate)
  if (!computed || !rate) return null
  const basis = operation.slots.find((slot) => slot.code !== computed.code)
  if (!basis) return null
  return { basis, computed, rate }
}

export function currencyByCode(
  currencies: Currency[],
  code: string | null | undefined,
): Currency | undefined {
  return currencies.find((currency) => currency.code === code)
}

export function currencyOptions(
  currencies: Currency[],
  exclude: string[] = [],
): { value: string; label: string }[] {
  return currencies
    .filter((currency) => !exclude.includes(currency.code))
    .map((currency) => ({ value: currency.code, label: `${currency.code} — ${currency.name}` }))
}

export function parseAmount(value: string): number {
  const normalized = value.replace(',', '.').trim()
  if (!normalized) return 0
  const parsed = Number(normalized)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
}

export function formatAmount(value: number, currencyCode: string, currencies: Currency[]): string {
  const minorUnits = currencyByCode(currencies, currencyCode)?.minor_units ?? 2
  return value.toFixed(minorUnits)
}

export function formatRate(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return ''
  return value.toFixed(8).replace(/0+$/, '').replace(/\.$/, '')
}

function rateOf(
  rates: WorkplaceRate[],
  currency: string,
  rateType: string,
): number | null {
  const row = rates.find(
    (rate) => rate.currency === currency && rate.rate_type === rateType,
  )
  if (!row) return null
  const value = Number(row.value_per_unit)
  return Number.isFinite(value) && value > 0 ? value : null
}

function directPairRate(
  rates: WorkplaceRate[],
  source: string,
  target: string,
): number | null {
  const buying = rates.find(
    (rate) =>
      rate.currency === source &&
      rate.base_currency === target &&
      rate.rate_type === 'conversion_buy',
  )
  if (buying) {
    const value = Number(buying.value_per_unit)
    if (Number.isFinite(value) && value > 0) return value
  }

  const selling = rates.find(
    (rate) =>
      rate.currency === target &&
      rate.base_currency === source &&
      rate.rate_type === 'conversion_sell',
  )
  if (selling) {
    const value = Number(selling.value_per_unit)
    if (Number.isFinite(value) && value > 0) return 1 / value
  }
  return null
}

function directRate(
  rates: WorkplaceRate[],
  source: string,
  target: string,
  rateType: string,
): number | null {
  const direct = rates.find(
    (rate) =>
      rate.currency === source &&
      rate.base_currency === target &&
      rate.rate_type === rateType,
  )
  if (direct) {
    const value = Number(direct.value_per_unit)
    if (Number.isFinite(value) && value > 0) return value
  }

  const reverse = rates.find(
    (rate) =>
      rate.currency === target &&
      rate.base_currency === source &&
      rate.rate_type === rateType,
  )
  if (reverse) {
    const value = Number(reverse.value_per_unit)
    if (Number.isFinite(value) && value > 0) return 1 / value
  }
  return null
}

export function resolveRate(
  context: WorkplaceContext,
  operation: WorkplaceOperation,
  source: string,
  target: string,
): number | null {
  const rateType = operation.rate_type
  if (!rateType) return null

  if (operation.rate_principle === 'buy') {
    return rateOf(context.rates, source, rateType)
  }
  if (operation.rate_principle === 'sell') {
    return rateOf(context.rates, target, rateType)
  }
  if (operation.rate_principle !== 'conversion') {
    return null
  }

  if (context.conversion_mode === 'direct') {
    const pair = directPairRate(context.rates, source, target)
    if (pair !== null) return pair
    const direct = directRate(context.rates, source, target, rateType)
    if (direct !== null) return direct
  }

  const base = context.base_currency
  const sourceRate = source === base ? 1 : rateOf(context.rates, source, rateType)
  const targetRate = target === base ? 1 : rateOf(context.rates, target, rateType)
  if (sourceRate === null || targetRate === null || targetRate === 0) return null
  return sourceRate / targetRate
}

export function computeAmount(
  basisAmount: number,
  rate: number,
  computation: string,
): number {
  if (!Number.isFinite(rate) || rate <= 0) return 0
  if (computation === 'divide') return basisAmount / rate
  return basisAmount * rate
}

export function slotCurrency(
  slot: SlotDef,
  baseCurrency: string,
  selected: string | null,
): string {
  if (slot.currency_policy === 'base') return baseCurrency
  if (slot.fixed_currency) return slot.fixed_currency
  return selected ?? ''
}
