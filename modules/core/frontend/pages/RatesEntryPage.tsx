import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconDeviceFloppy, IconInfoCircle, IconPlus, IconTrash } from '@tabler/icons-react'
import dayjs, { type Dayjs } from 'dayjs'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import type { BranchOption, CashDeskOption } from '@app/api/types'
import { useAuth } from '@app/auth/AuthContext'

import * as bankSettingsApi from '../api/bankSettings'
import type { ConversionMode } from '../api/bankSettings'
import * as branchesApi from '../api/branches'
import * as cashDesksApi from '../api/cashDesks'
import * as currencyConfigApi from '../api/currencyConfig'
import * as ratesApi from '../api/currencyRates'
import * as shiftsApi from '../api/shifts'

type Scope = ratesApi.RateScope
type EntryTab = 'rates' | 'conversion'

interface GridRow {
  currency: string
  units: string
  value: string
  original: string
  originalUnits: string
}

interface ConversionPairRow {
  key: number
  currency: string | null
  baseCurrency: string | null
  units: string
  buy: string
  sell: string
  originalCurrency: string | null
  originalBaseCurrency: string | null
  originalUnits: string
  originalBuy: string
  originalSell: string
}

const BANK = 'core.currency_rates.manage'
const OFFICIAL = 'core.currency_rates.manage.official'
const BRANCH = 'core.currency_rates.manage.branch'
const CASH_DESK = 'core.currency_rates.manage.cash_desk'
const CONVERSION_BUY = 'conversion_buy'
const CONVERSION_SELL = 'conversion_sell'

function makePair(key: number): ConversionPairRow {
  return {
    key,
    currency: null,
    baseCurrency: null,
    units: '1',
    buy: '',
    sell: '',
    originalCurrency: null,
    originalBaseCurrency: null,
    originalUnits: '1',
    originalBuy: '',
    originalSell: '',
  }
}

function dateTimeAt(date: string, time: string): Dayjs {
  return dayjs(`${date}T${time}:00`)
}

async function configuredCurrencies(
  scope: Scope,
  branchId: number | null,
  cashDeskId: number | null,
): Promise<string[]> {
  try {
    if (scope === 'cash_desk' && cashDeskId) {
      const config = await currencyConfigApi.fetchCashDeskCurrencies(cashDeskId)
      return config.currencies.map((item) => item.code)
    }
    if (scope === 'branch' && branchId) {
      const template = await currencyConfigApi.fetchBranchCurrencyTemplate(branchId)
      if (template.defined) return template.currencies.map((item) => item.code)
      const bank = await currencyConfigApi.fetchBankCurrencyTemplate()
      return bank.defined ? bank.currencies.map((item) => item.code) : []
    }
    if (scope === 'bank') {
      const bank = await currencyConfigApi.fetchBankCurrencyTemplate()
      return bank.defined ? bank.currencies.map((item) => item.code) : []
    }
  } catch {
    // A cashier may not be allowed to read the cash desk configuration. The
    // editor then starts with the currencies that already have rates and lets
    // the user add any active currency.
  }
  return []
}

export function RatesEntryPage() {
  const { t } = useTranslation('core')
  const { hasPermission } = useAuth()

  const canBank = hasPermission(BANK)
  const canOfficial = hasPermission(OFFICIAL)
  const canBranch = hasPermission(BRANCH)
  const canCashDesk = hasPermission(CASH_DESK)
  const cashierOnly = canCashDesk && !canBank && !canBranch
  const canManageNonOfficial = canBank || canBranch || canCashDesk

  const [rateTypes, setRateTypes] = useState<ratesApi.RateType[]>([])
  const [currencies, setCurrencies] = useState<currencyConfigApi.CurrencyOption[]>([])
  const [branches, setBranches] = useState<BranchOption[]>([])
  const [cashDesks, setCashDesks] = useState<CashDeskOption[]>([])
  const [currentShiftDesk, setCurrentShiftDesk] = useState<CashDeskOption | null>(null)
  const [baseCurrency, setBaseCurrency] = useState('')
  const [conversionMode, setConversionMode] = useState<ConversionMode>('via_base')
  const [activeTab, setActiveTab] = useState<EntryTab>('rates')

  const [scope, setScope] = useState<Scope>('bank')
  const [branchId, setBranchId] = useState<string | null>(null)
  const [cashDeskId, setCashDeskId] = useState<string | null>(null)
  const [rateTypeCode, setRateTypeCode] = useState<string | null>(null)
  const [date, setDate] = useState(dayjs().format('YYYY-MM-DD'))
  const [time, setTime] = useState(dayjs().format('HH:mm'))

  const [rows, setRows] = useState<GridRow[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [addCurrency, setAddCurrency] = useState<string | null>(null)

  const [pairs, setPairs] = useState<ConversionPairRow[]>([])
  const [pairsLoading, setPairsLoading] = useState(false)
  const [pairsSaving, setPairsSaving] = useState(false)
  const pairSeq = useRef(0)

  const genericRateTypes = useMemo(
    () =>
      rateTypes.filter(
        (item) =>
          item.code !== CONVERSION_BUY &&
          item.code !== CONVERSION_SELL &&
          (conversionMode !== 'direct' || item.principle !== 'conversion'),
      ),
    [conversionMode, rateTypes],
  )
  const selectedRateType = genericRateTypes.find((item) => item.code === rateTypeCode) ?? null
  const conversionRateType = rateTypes.find((item) => item.code === CONVERSION_BUY) ?? null
  const conversionIsCalendarDay = conversionRateType?.validity === 'calendar_day'
  const isOfficial = activeTab === 'rates' && selectedRateType?.principle === 'official'
  const allowsDirect = conversionMode === 'direct'
  const isCalendarDay =
    activeTab === 'conversion'
      ? conversionIsCalendarDay
      : selectedRateType?.validity === 'calendar_day'

  const notifyError = useCallback(
    (error: unknown) =>
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      }),
    [t],
  )

  const availableScopes = useMemo<Scope[]>(() => {
    if (isOfficial) return canOfficial ? ['bank'] : []
    const result: Scope[] = []
    if (canBank) result.push('bank')
    if (canBranch) result.push('branch', 'cash_desk')
    else if (canCashDesk) result.push('cash_desk')
    return result
  }, [canBank, canBranch, canCashDesk, canOfficial, isOfficial])

  useEffect(() => {
    Promise.all([
      ratesApi.listRateTypes(),
      currencyConfigApi.listActiveCurrencies(),
      bankSettingsApi.fetchBankSettings(),
      branchesApi.listRateBranchOptions(),
      cashDesksApi.listRateCashDeskOptions(),
    ])
      .then(([types, catalogue, settings, branchRows, deskRows]) => {
        const visibleTypes = types.filter(
          (item) =>
            item.is_active &&
            (item.principle === 'official' ? canOfficial : canManageNonOfficial),
        )
        setRateTypes(visibleTypes)
        setCurrencies(catalogue)
        setBaseCurrency(settings.base_currency)
        setConversionMode(settings.conversion_mode)
        setBranches(branchRows)
        setCashDesks(deskRows)
        const genericTypes = visibleTypes.filter(
          (item) =>
            item.code !== CONVERSION_BUY &&
            item.code !== CONVERSION_SELL &&
            (settings.conversion_mode !== 'direct' || item.principle !== 'conversion'),
        )
        setRateTypeCode((current) => {
          if (current && genericTypes.some((item) => item.code === current)) return current
          return genericTypes[0]?.code ?? null
        })
        if (canBank) {
          setScope('bank')
        } else if (canBranch) {
          setScope('branch')
        } else if (canCashDesk) {
          setScope('cash_desk')
        }
      })
      .catch(notifyError)
  }, [canBank, canBranch, canCashDesk, canOfficial, canManageNonOfficial, notifyError])

  useEffect(() => {
    if (!cashierOnly) return
    shiftsApi
      .fetchCurrentShift()
      .then((shift) => {
        if (shift) {
          setBranchId(String(shift.cash_desk_branch))
          setCashDeskId(String(shift.cash_desk))
          setCurrentShiftDesk({
            id: shift.cash_desk,
            name: shift.cash_desk_name,
            code: shift.cash_desk_code,
            branch: shift.cash_desk_branch,
          })
        }
      })
      .catch(() => undefined)
  }, [cashierOnly])

  useEffect(() => {
    if (availableScopes.length && !availableScopes.includes(scope)) {
      setScope(availableScopes[0])
    }
  }, [availableScopes, scope])

  useEffect(() => {
    if (isOfficial) setScope('bank')
  }, [isOfficial])

  useEffect(() => {
    if (!allowsDirect) setActiveTab('rates')
  }, [allowsDirect])

  useEffect(() => {
    if (rateTypeCode && genericRateTypes.some((item) => item.code === rateTypeCode)) return
    setRateTypeCode(genericRateTypes[0]?.code ?? null)
  }, [genericRateTypes, rateTypeCode])

  const branchOptions = useMemo(
    () =>
      branches.map((branch) => ({
        value: String(branch.id),
        label: branch.code ? `${branch.name} (${branch.code})` : branch.name,
      })),
    [branches],
  )

  const cashDeskOptions = useMemo(() => {
    const desks = currentShiftDesk
      ? [
          ...cashDesks.filter((desk) => desk.id !== currentShiftDesk.id),
          currentShiftDesk,
        ]
      : cashDesks
    return desks
      .filter((desk) => !branchId || String(desk.branch) === branchId)
      .map((desk) => ({
        value: String(desk.id),
        label: desk.code ? `${desk.name} (${desk.code})` : desk.name,
      }))
  }, [branchId, cashDesks, currentShiftDesk])

  const currencyByCode = useMemo(
    () => Object.fromEntries(currencies.map((item) => [item.code, item])),
    [currencies],
  )

  const pairCurrencyOptions = useMemo(
    () =>
      currencies.map((item) => ({
        value: item.code,
        label: `${item.code} — ${item.name}`,
      })),
    [currencies],
  )

  const rateTypeOptions = useMemo(
    () =>
      genericRateTypes.map((item) => ({ value: item.code, label: item.name })),
    [genericRateTypes],
  )

  const loadGrid = useCallback(async () => {
    if (activeTab !== 'rates') return
    if (!selectedRateType) {
      setRows([])
      return
    }
    if (scope === 'branch' && !branchId) {
      setRows([])
      return
    }
    if (scope === 'cash_desk' && !cashDeskId) {
      setRows([])
      return
    }
    setLoading(true)
    try {
      const moment = isCalendarDay
        ? dayjs(`${date}T12:00:00`).toISOString()
        : dateTimeAt(date, time).toISOString()
      const [effective, configured] = await Promise.all([
        ratesApi.listAllCurrentRates({
          rate_type: selectedRateType.code,
          base_currency: baseCurrency,
          scope,
          branch: scope === 'branch' && branchId ? Number(branchId) : '',
          cash_desk: scope === 'cash_desk' && cashDeskId ? Number(cashDeskId) : '',
          at: moment,
        }),
        configuredCurrencies(
          scope,
          branchId ? Number(branchId) : null,
          cashDeskId ? Number(cashDeskId) : null,
        ),
      ])
      const byCurrency = new Map(effective.map((rate) => [rate.currency, rate]))
      const codes = Array.from(new Set([...configured, ...byCurrency.keys()]))
        .filter((code) => code !== baseCurrency)
        .sort()
      setRows(
        codes.map((currency) => {
          const rate = byCurrency.get(currency)
          const value = rate?.value ?? ''
          const units = String(rate?.units ?? 1)
          return { currency, units, value, original: value, originalUnits: units }
        }),
      )
    } catch (error) {
      notifyError(error)
    } finally {
      setLoading(false)
    }
  }, [
    activeTab,
    baseCurrency,
    branchId,
    cashDeskId,
    date,
    isCalendarDay,
    notifyError,
    scope,
    selectedRateType,
    time,
  ])

  useEffect(() => {
    void loadGrid()
  }, [loadGrid])

  const currencyOptions = useMemo(() => {
    const used = new Set(rows.map((row) => row.currency))
    return currencies
      .filter((item) => !used.has(item.code) && item.code !== baseCurrency)
      .map((item) => ({ value: item.code, label: `${item.code} — ${item.name}` }))
  }, [baseCurrency, currencies, rows])

  const addRow = () => {
    if (!addCurrency || rows.some((row) => row.currency === addCurrency)) return
    setRows((current) =>
      [
        ...current,
        { currency: addCurrency, units: '1', value: '', original: '', originalUnits: '1' },
      ].sort((a, b) => a.currency.localeCompare(b.currency)),
    )
    setAddCurrency(null)
  }

  const setValue = (currency: string, value: string) => {
    setRows((current) =>
      current.map((row) => (row.currency === currency ? { ...row, value } : row)),
    )
  }

  const setUnits = (currency: string, units: string) => {
    setRows((current) =>
      current.map((row) => (row.currency === currency ? { ...row, units } : row)),
    )
  }

  const saveRates = async () => {
    if (!selectedRateType) return
    const items = rows
      .filter(
        (row) =>
          row.value.trim() !== '' &&
          (row.value.trim() !== row.original.trim() || row.units !== row.originalUnits),
      )
      .map((row) => ({
        currency: row.currency,
        units: Math.max(1, Number(row.units) || 1),
        value: row.value.trim(),
      }))
    if (!items.length) {
      notifications.show({ color: 'red', title: t('common.error'), message: t('ratesEntry.nothingToSave') })
      return
    }
    setSaving(true)
    try {
      await ratesApi.bulkSetRates({
        rate_type: selectedRateType.code,
        base_currency: baseCurrency,
        branch: scope === 'branch' && branchId ? Number(branchId) : null,
        cash_desk: scope === 'cash_desk' && cashDeskId ? Number(cashDeskId) : null,
        effective_date: isCalendarDay ? date : null,
        effective_from: isCalendarDay ? null : dateTimeAt(date, time).toISOString(),
        items,
      })
      notifications.show({ color: 'green', message: t('ratesEntry.saved') })
      await loadGrid()
    } catch (error) {
      notifyError(error)
    } finally {
      setSaving(false)
    }
  }

  const nextPairKey = () => {
    pairSeq.current += 1
    return pairSeq.current
  }

  const loadPairs = useCallback(async () => {
    if (!allowsDirect || activeTab !== 'conversion') return
    if (scope === 'branch' && !branchId) {
      setPairs([])
      return
    }
    if (scope === 'cash_desk' && !cashDeskId) {
      setPairs([])
      return
    }
    setPairsLoading(true)
    try {
      const moment = conversionIsCalendarDay
        ? dayjs(`${date}T12:00:00`).toISOString()
        : dateTimeAt(date, time).toISOString()
      const scopeFilters: ratesApi.RateFilters = {
        scope,
        branch: scope === 'branch' && branchId ? Number(branchId) : '',
        cash_desk: scope === 'cash_desk' && cashDeskId ? Number(cashDeskId) : '',
        at: moment,
      }
      const [buyRates, sellRates] = await Promise.all([
        ratesApi.listAllCurrentRates({ ...scopeFilters, rate_type: CONVERSION_BUY }),
        ratesApi.listAllCurrentRates({ ...scopeFilters, rate_type: CONVERSION_SELL }),
      ])
      const buyByPair = new Map(
        buyRates.map((rate) => [`${rate.currency}/${rate.base_currency}`, rate]),
      )
      const sellByPair = new Map(
        sellRates.map((rate) => [`${rate.currency}/${rate.base_currency}`, rate]),
      )
      const pairKeys = Array.from(
        new Set([...buyByPair.keys(), ...sellByPair.keys()]),
      ).sort()
      const loaded = pairKeys.map((key) => {
        const buy = buyByPair.get(key)
        const sell = sellByPair.get(key)
        const currency = buy?.currency ?? sell?.currency ?? ''
        const baseCurrency = buy?.base_currency ?? sell?.base_currency ?? ''
        const units = String(buy?.units ?? sell?.units ?? 1)
        const buyValue = buy?.value ?? ''
        const sellValue = sell?.value ?? ''
        return {
          key: nextPairKey(),
          currency,
          baseCurrency,
          units,
          buy: buyValue,
          sell: sellValue,
          originalCurrency: currency,
          originalBaseCurrency: baseCurrency,
          originalUnits: units,
          originalBuy: buyValue,
          originalSell: sellValue,
        }
      })
      setPairs(loaded.length ? loaded : [makePair(nextPairKey())])
    } catch (error) {
      notifyError(error)
    } finally {
      setPairsLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeTab,
    allowsDirect,
    branchId,
    cashDeskId,
    conversionIsCalendarDay,
    date,
    notifyError,
    scope,
    time,
  ])

  useEffect(() => {
    void loadPairs()
  }, [loadPairs])

  const addPair = () => {
    setPairs((current) => [...current, makePair(nextPairKey())])
  }

  const removePair = (key: number) => {
    setPairs((current) => current.filter((row) => row.key !== key))
  }

  const setPairField = (
    key: number,
    patch: Partial<
      Pick<ConversionPairRow, 'currency' | 'baseCurrency' | 'units' | 'buy' | 'sell'>
    >,
  ) => {
    setPairs((current) =>
      current.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    )
  }

  const saveConversion = async () => {
    if (!allowsDirect) return
    const filled = pairs.filter(
      (row) =>
        row.currency ||
        row.baseCurrency ||
        row.buy.trim() ||
        row.sell.trim(),
    )
    if (!filled.length) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: t('ratesEntry.nothingToSave'),
      })
      return
    }

    const payloadPairs: ratesApi.ConversionPairItem[] = []
    for (const row of filled) {
      if (!row.currency || !row.baseCurrency) {
        notifications.show({
          color: 'red',
          title: t('common.error'),
          message: t('ratesEntry.conversion.pairIncomplete'),
        })
        return
      }
      if (row.currency === row.baseCurrency) {
        notifications.show({
          color: 'red',
          title: t('common.error'),
          message: t('ratesEntry.conversion.sameCurrency'),
        })
        return
      }
      if (!row.buy.trim() || !row.sell.trim()) {
        notifications.show({
          color: 'red',
          title: t('common.error'),
          message: t('ratesEntry.conversion.valuesRequired'),
        })
        return
      }
      const changed =
        row.currency !== row.originalCurrency ||
        row.baseCurrency !== row.originalBaseCurrency ||
        row.units !== row.originalUnits ||
        row.buy.trim() !== row.originalBuy.trim() ||
        row.sell.trim() !== row.originalSell.trim()
      if (changed) {
        payloadPairs.push({
          currency: row.currency,
          base_currency: row.baseCurrency,
          units: Math.max(1, Number(row.units) || 1),
          buy: row.buy.trim(),
          sell: row.sell.trim(),
        })
      }
    }
    if (!payloadPairs.length) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: t('ratesEntry.nothingToSave'),
      })
      return
    }

    setPairsSaving(true)
    try {
      await ratesApi.conversionBulkSet({
        branch: scope === 'branch' && branchId ? Number(branchId) : null,
        cash_desk: scope === 'cash_desk' && cashDeskId ? Number(cashDeskId) : null,
        effective_date: conversionIsCalendarDay ? date : null,
        effective_from: conversionIsCalendarDay
          ? null
          : dateTimeAt(date, time).toISOString(),
        pairs: payloadPairs,
      })
      notifications.show({ color: 'green', message: t('ratesEntry.conversion.saved') })
      await loadPairs()
    } catch (error) {
      notifyError(error)
    } finally {
      setPairsSaving(false)
    }
  }

  const scopeLabel = t(`ratesEntry.scopes.${scope}`)
  const scopeDisabled = cashierOnly || availableScopes.length <= 1
  const scopeReady =
    Boolean(date) &&
    (isCalendarDay || Boolean(time)) &&
    (scope === 'bank' ||
      (scope === 'branch' && Boolean(branchId)) ||
      (scope === 'cash_desk' && Boolean(cashDeskId)))
  const canEdit =
    activeTab === 'conversion'
      ? allowsDirect && canManageNonOfficial && !pairsLoading && scopeReady
      : Boolean(selectedRateType) && !loading && scopeReady
  const saveActive = activeTab === 'conversion' ? saveConversion : saveRates
  const savingActive = activeTab === 'conversion' ? pairsSaving : saving

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>{t('ratesEntry.title')}</Title>
        <Button
          leftSection={<IconDeviceFloppy size={16} />}
          loading={savingActive}
          disabled={!canEdit}
          onClick={() => void saveActive()}
        >
          {t('common.save')}
        </Button>
      </Group>

      {allowsDirect && (
        <SegmentedControl
          value={activeTab}
          onChange={(value) => setActiveTab(value as EntryTab)}
          data={[
            { value: 'rates', label: t('ratesEntry.tabs.rates') },
            { value: 'conversion', label: t('ratesEntry.tabs.conversion') },
          ]}
        />
      )}

      <Card withBorder padding="md" radius="md">
        <Stack gap="sm">
          <Group grow align="flex-start">
            <Select
              label={t('ratesEntry.scope')}
              data={availableScopes.map((value) => ({
                value,
                label: t(`ratesEntry.scopes.${value}`),
              }))}
              value={scope}
              onChange={(value) => value && setScope(value as Scope)}
              disabled={scopeDisabled}
              allowDeselect={false}
            />
            {activeTab === 'rates' && (
              <Select
                label={t('ratesEntry.rateType')}
                data={rateTypeOptions}
                value={rateTypeCode}
                onChange={setRateTypeCode}
                allowDeselect={false}
              />
            )}
          </Group>

          {scope === 'branch' && (
            <Select
              label={t('ratesEntry.branch')}
              data={branchOptions}
              value={branchId}
              onChange={(value) => {
                setBranchId(value)
                setCashDeskId(null)
              }}
              searchable
              required
            />
          )}

          {scope === 'cash_desk' && (
            <Group grow align="flex-start">
              {!cashierOnly && (
                <Select
                  label={t('ratesEntry.branch')}
                  data={branchOptions}
                  value={branchId}
                  onChange={(value) => {
                    setBranchId(value)
                    setCashDeskId(null)
                  }}
                  searchable
                  required
                />
              )}
              <Select
                label={t('ratesEntry.cashDesk')}
                data={cashDeskOptions}
                value={cashDeskId}
                onChange={setCashDeskId}
                searchable
                required
                disabled={cashierOnly}
              />
            </Group>
          )}

          <Group grow align="flex-start">
            <TextInput
              label={t('ratesEntry.date')}
              type="date"
              value={date}
              onChange={(event) => setDate(event.currentTarget.value)}
              required
            />
            {!isCalendarDay && (
              <TextInput
                label={t('ratesEntry.time')}
                type="time"
                value={time}
                onChange={(event) => setTime(event.currentTarget.value)}
                required
              />
            )}
          </Group>

          <Group gap="xs">
            <Badge variant="light">
              {activeTab === 'conversion'
                ? t('ratesEntry.conversion.badge')
                : t('ratesEntry.baseCurrency', { currency: baseCurrency })}
            </Badge>
            <Badge variant="light">{scopeLabel}</Badge>
            {activeTab === 'rates' && selectedRateType && (
              <Badge variant="light">
                {t('ratesEntry.validityHint', {
                  validity: t(`ratesEntry.validity.${selectedRateType.validity}`),
                })}
              </Badge>
            )}
            {activeTab === 'conversion' && conversionRateType && (
              <Badge variant="light">
                {t('ratesEntry.validityHint', {
                  validity: t(`ratesEntry.validity.${conversionRateType.validity}`),
                })}
              </Badge>
            )}
          </Group>
        </Stack>
      </Card>

      {cashierOnly && !cashDeskId && (
        <Alert color="yellow" icon={<IconInfoCircle size={16} />}>
          {t('ratesEntry.noOpenShift')}
        </Alert>
      )}

      {activeTab === 'rates' ? (
        <>
          <Group justify="space-between">
            <Text fw={500}>{t('ratesEntry.gridTitle')}</Text>
            <Group gap="xs">
              <Select
                placeholder={t('ratesEntry.addCurrency')}
                data={currencyOptions}
                value={addCurrency}
                onChange={setAddCurrency}
                searchable
                clearable
                w={260}
              />
              <Button
                variant="default"
                leftSection={<IconPlus size={16} />}
                disabled={!addCurrency}
                onClick={addRow}
              >
                {t('common.add')}
              </Button>
            </Group>
          </Group>

          <Table striped highlightOnHover withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('ratesEntry.columns.currency')}</Table.Th>
                <Table.Th>{t('ratesEntry.columns.units')}</Table.Th>
                <Table.Th>{t('ratesEntry.columns.value', { currency: baseCurrency })}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {loading ? (
                <Table.Tr>
                  <Table.Td colSpan={3}>
                    <Text c="dimmed" ta="center" py="md">
                      {t('ratesEntry.loading')}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : rows.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={3}>
                    <Text c="dimmed" ta="center" py="md">
                      {t('ratesEntry.empty')}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                rows.map((row) => (
                  <Table.Tr key={row.currency}>
                    <Table.Td>
                      <Text fw={500}>{row.currency}</Text>
                      {currencyByCode[row.currency] && (
                        <Text size="xs" c="dimmed">
                          {currencyByCode[row.currency].name}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <NumberInput
                        value={row.units}
                        onChange={(value) =>
                          setUnits(row.currency, value === '' ? '' : String(value))
                        }
                        min={1}
                        decimalScale={0}
                        allowNegative={false}
                        w={110}
                      />
                    </Table.Td>
                    <Table.Td>
                      <NumberInput
                        value={row.value}
                        onChange={(value) =>
                          setValue(row.currency, value === '' ? '' : String(value))
                        }
                        decimalScale={6}
                        fixedDecimalScale={false}
                        allowNegative={false}
                        placeholder="0.000000"
                        w={220}
                      />
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        </>
      ) : (
        <>
          <Group justify="space-between">
            <Text fw={500}>{t('ratesEntry.conversion.title')}</Text>
            <Button
              variant="default"
              leftSection={<IconPlus size={16} />}
              onClick={addPair}
              disabled={pairsLoading}
            >
              {t('ratesEntry.conversion.addPair')}
            </Button>
          </Group>

          <Text size="xs" c="dimmed">
            {t('ratesEntry.conversion.hint')}
          </Text>

          <Table striped highlightOnHover withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('ratesEntry.conversion.columns.currency')}</Table.Th>
                <Table.Th>{t('ratesEntry.conversion.columns.quote')}</Table.Th>
                <Table.Th>{t('ratesEntry.conversion.columns.units')}</Table.Th>
                <Table.Th>{t('ratesEntry.conversion.columns.buy')}</Table.Th>
                <Table.Th>{t('ratesEntry.conversion.columns.sell')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {pairsLoading ? (
                <Table.Tr>
                  <Table.Td colSpan={6}>
                    <Text c="dimmed" ta="center" py="md">
                      {t('ratesEntry.loading')}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : pairs.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={6}>
                    <Text c="dimmed" ta="center" py="md">
                      {t('ratesEntry.conversion.empty')}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                pairs.map((row) => (
                  <Table.Tr key={row.key}>
                    <Table.Td>
                      <Select
                        placeholder={t('ratesEntry.conversion.columns.currency')}
                        data={pairCurrencyOptions}
                        value={row.currency}
                        onChange={(value) =>
                          setPairField(row.key, { currency: value, buy: '', sell: '' })
                        }
                        searchable
                        w={170}
                      />
                    </Table.Td>
                    <Table.Td>
                      <Select
                        placeholder={t('ratesEntry.conversion.columns.quote')}
                        data={pairCurrencyOptions}
                        value={row.baseCurrency}
                        onChange={(value) =>
                          setPairField(row.key, { baseCurrency: value, buy: '', sell: '' })
                        }
                        searchable
                        w={170}
                      />
                    </Table.Td>
                    <Table.Td>
                      <NumberInput
                        value={row.units}
                        onChange={(value) =>
                          setPairField(row.key, { units: value === '' ? '' : String(value) })
                        }
                        min={1}
                        decimalScale={0}
                        allowNegative={false}
                        w={100}
                      />
                    </Table.Td>
                    <Table.Td>
                      <NumberInput
                        value={row.buy}
                        onChange={(value) =>
                          setPairField(row.key, { buy: value === '' ? '' : String(value) })
                        }
                        decimalScale={6}
                        fixedDecimalScale={false}
                        allowNegative={false}
                        placeholder="0.000000"
                        w={170}
                      />
                    </Table.Td>
                    <Table.Td>
                      <NumberInput
                        value={row.sell}
                        onChange={(value) =>
                          setPairField(row.key, { sell: value === '' ? '' : String(value) })
                        }
                        decimalScale={6}
                        fixedDecimalScale={false}
                        allowNegative={false}
                        placeholder="0.000000"
                        w={170}
                      />
                    </Table.Td>
                    <Table.Td>
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        aria-label={t('common.delete')}
                        onClick={() => removePair(row.key)}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        </>
      )}
    </Stack>
  )
}
