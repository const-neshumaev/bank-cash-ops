import {
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Pagination,
  Select,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconRefresh } from '@tabler/icons-react'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import type { BranchOption, CashDeskOption } from '@app/api/types'

import * as branchesApi from '../api/branches'
import * as cashDesksApi from '../api/cashDesks'
import * as currencyConfigApi from '../api/currencyConfig'
import * as ratesApi from '../api/currencyRates'

const PAGE_SIZE = 20

function formatMoment(value: string | null): string {
  return value ? dayjs(value).format('DD.MM.YYYY HH:mm') : '—'
}

function formatDay(value: string | null): string {
  return value ? dayjs(value).format('DD.MM.YYYY') : '—'
}

export function CurrentRatesPage() {
  const { t } = useTranslation('core')

  const [rates, setRates] = useState<ratesApi.CurrencyRate[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const [rateTypes, setRateTypes] = useState<ratesApi.RateType[]>([])
  const [currencies, setCurrencies] = useState<currencyConfigApi.CurrencyOption[]>([])
  const [branches, setBranches] = useState<BranchOption[]>([])
  const [cashDesks, setCashDesks] = useState<CashDeskOption[]>([])

  const [currency, setCurrency] = useState<string | null>(null)
  const [baseCurrency, setBaseCurrency] = useState<string | null>(null)
  const [rateType, setRateType] = useState<string | null>(null)
  const [scope, setScope] = useState<ratesApi.RateScope | null>(null)
  const [branchId, setBranchId] = useState<string | null>(null)
  const [cashDeskId, setCashDeskId] = useState<string | null>(null)

  const notifyError = useCallback(
    (error: unknown) =>
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      }),
    [t],
  )

  useEffect(() => {
    Promise.all([
      ratesApi.listRateTypes(),
      currencyConfigApi.listActiveCurrencies(),
      branchesApi.listRateBranchOptions(),
    ])
      .then(([types, catalogue, branchRows]) => {
        setRateTypes(types)
        setCurrencies(catalogue)
        setBranches(branchRows)
      })
      .catch(notifyError)
  }, [notifyError])

  useEffect(() => {
    cashDesksApi
      .listRateCashDeskOptions(branchId ? Number(branchId) : undefined)
      .then(setCashDesks)
      .catch(() => setCashDesks([]))
  }, [branchId])

  const rateTypeByCode = useMemo(
    () => Object.fromEntries(rateTypes.map((item) => [item.code, item])),
    [rateTypes],
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await ratesApi.listCurrentRates({
        page,
        pageSize: PAGE_SIZE,
        currency: currency ?? '',
        base_currency: baseCurrency ?? '',
        rate_type: rateType ?? '',
        scope: scope ?? '',
        branch: branchId ? Number(branchId) : '',
        cash_desk: cashDeskId ? Number(cashDeskId) : '',
      })
      setRates(data.results)
      setTotal(data.count)
    } catch (error) {
      notifyError(error)
    } finally {
      setLoading(false)
    }
  }, [
    baseCurrency,
    branchId,
    cashDeskId,
    currency,
    notifyError,
    page,
    rateType,
    scope,
  ])

  useEffect(() => {
    void load()
  }, [load])

  const branchOptions = branches.map((branch) => ({
    value: String(branch.id),
    label: branch.code ? `${branch.name} (${branch.code})` : branch.name,
  }))

  const cashDeskOptions = cashDesks
    .filter((desk) => !branchId || String(desk.branch) === branchId)
    .map((desk) => ({
      value: String(desk.id),
      label: desk.code ? `${desk.name} (${desk.code})` : desk.name,
    }))

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <Stack>
      <Group justify="space-between">
        <div>
          <Title order={3}>{t('currentRates.title')}</Title>
          <Text size="sm" c="dimmed">
            {t('currentRates.hint')}
          </Text>
        </div>
        <Button
          variant="default"
          leftSection={<IconRefresh size={16} />}
          onClick={() => void load()}
        >
          {t('currentRates.refresh')}
        </Button>
      </Group>

      <Group align="flex-end">
        <Select
          label={t('currentRates.currency')}
          data={currencies.map((item) => ({
            value: item.code,
            label: `${item.code} — ${item.name}`,
          }))}
          value={currency}
          onChange={(value) => {
            setCurrency(value)
            setPage(1)
          }}
          searchable
          clearable
          w={220}
        />
        <Select
          label={t('currentRates.quoteCurrency')}
          data={currencies.map((item) => ({
            value: item.code,
            label: `${item.code} — ${item.name}`,
          }))}
          value={baseCurrency}
          onChange={(value) => {
            setBaseCurrency(value)
            setPage(1)
          }}
          searchable
          clearable
          w={220}
        />
        <Select
          label={t('currentRates.rateType')}
          data={rateTypes.map((item) => ({ value: item.code, label: item.name }))}
          value={rateType}
          onChange={(value) => {
            setRateType(value)
            setPage(1)
          }}
          clearable
          w={220}
        />
        <Select
          label={t('currentRates.scope')}
          data={[
            { value: 'bank', label: t('currentRates.scopes.bank') },
            { value: 'branch', label: t('currentRates.scopes.branch') },
            { value: 'cash_desk', label: t('currentRates.scopes.cash_desk') },
          ]}
          value={scope}
          onChange={(value) => {
            setScope(value as ratesApi.RateScope | null)
            setPage(1)
          }}
          clearable
          w={180}
        />
        <Select
          label={t('currentRates.branch')}
          data={branchOptions}
          value={branchId}
          onChange={(value) => {
            setBranchId(value)
            setCashDeskId(null)
            setPage(1)
          }}
          clearable
          searchable
          w={220}
        />
        <Select
          label={t('currentRates.cashDesk')}
          data={cashDeskOptions}
          value={cashDeskId}
          onChange={(value) => {
            setCashDeskId(value)
            setPage(1)
          }}
          clearable
          searchable
          w={220}
        />
      </Group>

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('currentRates.columns.currency')}</Table.Th>
            <Table.Th>{t('currentRates.columns.rateType')}</Table.Th>
            <Table.Th>{t('currentRates.columns.units')}</Table.Th>
            <Table.Th>{t('currentRates.columns.value')}</Table.Th>
            <Table.Th>{t('currentRates.columns.scope')}</Table.Th>
            <Table.Th>{t('currentRates.columns.effective')}</Table.Th>
            <Table.Th>{t('currentRates.columns.author')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {loading ? (
            <Table.Tr>
              <Table.Td colSpan={7}>
                <Center py="md">
                  <Loader size="sm" />
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : rates.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={7}>
                <Center py="md">
                  <Text c="dimmed">{t('currentRates.empty')}</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            rates.map((rate) => (
              <Table.Tr key={rate.id}>
                <Table.Td>{rate.currency}</Table.Td>
                <Table.Td>{rateTypeByCode[rate.rate_type]?.name ?? rate.rate_type}</Table.Td>
                <Table.Td>{rate.units}</Table.Td>
                <Table.Td>
                  {rate.value} {rate.base_currency}
                </Table.Td>
                <Table.Td>
                  <Badge variant="light">{t(`currentRates.scopes.${rate.scope}`)}</Badge>
                  {(rate.branch_name || rate.cash_desk_name) && (
                    <Text size="xs" c="dimmed">
                      {rate.cash_desk_name ?? rate.branch_name}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {rate.effective_date
                    ? formatDay(rate.effective_date)
                    : formatMoment(rate.effective_from)}
                </Table.Td>
                <Table.Td>{rate.created_by_email ?? '—'}</Table.Td>
              </Table.Tr>
            ))
          )}
        </Table.Tbody>
      </Table>

      {pageCount > 1 && (
        <Center>
          <Pagination value={page} total={pageCount} onChange={setPage} />
        </Center>
      )}
    </Stack>
  )
}
