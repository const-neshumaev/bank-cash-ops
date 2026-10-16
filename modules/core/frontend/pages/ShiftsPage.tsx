import {
  ActionIcon,
  Badge,
  Center,
  Group,
  Loader,
  Pagination,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import dayjs from 'dayjs'
import { notifications } from '@mantine/notifications'
import { IconLock } from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import type { BranchOption, CashDeskOption, Shift } from '@app/api/types'
import { useAuth } from '@app/auth/AuthContext'

import * as branchesApi from '../api/branches'
import * as cashDesksApi from '../api/cashDesks'
import * as shiftsApi from '../api/shifts'

const PAGE_SIZE = 20

const STATUS_OPTIONS = [
  { value: 'open', labelKey: 'shifts.statusOpen' },
  { value: 'closed', labelKey: 'shifts.statusClosed' },
]

type PeriodValue = '7' | '30' | '90' | 'all' | 'custom'

const PERIOD_OPTIONS = [
  { value: '7', labelKey: 'shifts.period7' },
  { value: '30', labelKey: 'shifts.period30' },
  { value: '90', labelKey: 'shifts.period90' },
  { value: 'all', labelKey: 'shifts.periodAll' },
  { value: 'custom', labelKey: 'shifts.periodCustom' },
]

const COLUMN_COUNT = 7

function formatDateTime(value: string | null): string {
  return value ? dayjs(value).format('DD.MM.YYYY HH:mm') : '—'
}

function cashDeskLabel(name: string, code: string | null): string {
  return code ? `${name} (${code})` : name
}

export function ShiftsPage() {
  const { t } = useTranslation('core')
  const { hasPermission } = useAuth()
  const canManage = hasPermission('core.shifts.manage')

  const [shifts, setShifts] = useState<Shift[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [period, setPeriod] = useState<PeriodValue>('30')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [branchFilter, setBranchFilter] = useState<string | null>(null)
  const [cashDeskFilter, setCashDeskFilter] = useState<string | null>(null)

  const [branches, setBranches] = useState<BranchOption[]>([])
  const [cashDesks, setCashDesks] = useState<CashDeskOption[]>([])
  const [branchSearch, setBranchSearch] = useState('')
  const [deskSearch, setDeskSearch] = useState('')
  const [debouncedBranchSearch] = useDebouncedValue(branchSearch, 300)
  const [debouncedDeskSearch] = useDebouncedValue(deskSearch, 300)

  const { openedFrom, openedTo } = useMemo(() => {
    if (period === 'all') {
      return { openedFrom: undefined, openedTo: undefined }
    }
    if (period === 'custom') {
      return {
        openedFrom: customFrom ? dayjs(customFrom).startOf('day').toISOString() : undefined,
        openedTo: customTo ? dayjs(customTo).endOf('day').toISOString() : undefined,
      }
    }
    return {
      openedFrom: dayjs()
        .subtract(Number(period), 'day')
        .startOf('day')
        .toISOString(),
      openedTo: undefined,
    }
  }, [period, customFrom, customTo])

  useEffect(() => {
    void branchesApi
      .listSelectableBranches(debouncedBranchSearch)
      .then(setBranches)
      .catch(() => setBranches([]))
  }, [debouncedBranchSearch])

  useEffect(() => {
    if (!branchFilter) {
      setCashDesks([])
      return
    }
    void cashDesksApi
      .listSelectableCashDesks(Number(branchFilter), debouncedDeskSearch)
      .then(setCashDesks)
      .catch(() => setCashDesks([]))
  }, [branchFilter, debouncedDeskSearch])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await shiftsApi.listShifts({
        page,
        pageSize: PAGE_SIZE,
        status: statusFilter ?? '',
        branch: branchFilter ? Number(branchFilter) : '',
        cashDesk: cashDeskFilter ? Number(cashDeskFilter) : '',
        openedFrom,
        openedTo,
      })
      setShifts(data.results)
      setTotal(data.count)
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter, branchFilter, cashDeskFilter, openedFrom, openedTo])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setPage(1)
  }, [statusFilter, branchFilter, cashDeskFilter, openedFrom, openedTo])

  const handleForceClose = async (shift: Shift) => {
    try {
      await shiftsApi.forceCloseShift(shift.id)
      notifications.show({ color: 'green', message: t('shifts.closedMessage') })
      void load()
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>{t('shifts.title')}</Title>
      </Group>

      <Group align="flex-end">
        <Select
          label={t('shifts.period')}
          data={PERIOD_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }))}
          value={period}
          onChange={(value) => setPeriod((value as PeriodValue) ?? '30')}
          w={200}
        />
        {period === 'custom' && (
          <>
            <TextInput
              type="date"
              label={t('shifts.dateFrom')}
              value={customFrom}
              onChange={(event) => setCustomFrom(event.currentTarget.value)}
              w={160}
            />
            <TextInput
              type="date"
              label={t('shifts.dateTo')}
              value={customTo}
              onChange={(event) => setCustomTo(event.currentTarget.value)}
              w={160}
            />
          </>
        )}
        <Select
          label={t('shifts.status')}
          placeholder={t('shifts.anyStatus')}
          data={STATUS_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }))}
          value={statusFilter}
          onChange={setStatusFilter}
          clearable
          w={160}
        />
        <Select
          label={t('shifts.branch')}
          placeholder={t('shifts.allBranches')}
          data={branches.map((branch) => ({
            value: String(branch.id),
            label: branch.code ? `${branch.name} (${branch.code})` : branch.name,
          }))}
          value={branchFilter}
          onChange={(value) => {
            setBranchFilter(value)
            setCashDeskFilter(null)
          }}
          searchable
          searchValue={branchSearch}
          onSearchChange={setBranchSearch}
          clearable
          w={240}
        />
        <Select
          label={t('shifts.cashDesk')}
          placeholder={branchFilter ? t('shifts.allCashDesks') : t('shifts.selectBranchFirst')}
          data={cashDesks.map((desk) => ({
            value: String(desk.id),
            label: cashDeskLabel(desk.name, desk.code),
          }))}
          value={cashDeskFilter}
          onChange={setCashDeskFilter}
          searchable
          searchValue={deskSearch}
          onSearchChange={setDeskSearch}
          disabled={!branchFilter}
          clearable
          w={240}
        />
      </Group>

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('shifts.columns.branch')}</Table.Th>
            <Table.Th>{t('shifts.columns.cashDesk')}</Table.Th>
            <Table.Th>{t('shifts.columns.cashier')}</Table.Th>
            <Table.Th>{t('shifts.columns.opened')}</Table.Th>
            <Table.Th>{t('shifts.columns.closed')}</Table.Th>
            <Table.Th>{t('shifts.columns.status')}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {loading ? (
            <Table.Tr>
              <Table.Td colSpan={COLUMN_COUNT}>
                <Center py="md">
                  <Loader size="sm" />
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : shifts.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={COLUMN_COUNT}>
                <Center py="md">
                  <Text c="dimmed">{t('shifts.empty')}</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            shifts.map((shift) => (
              <Table.Tr key={shift.id}>
                <Table.Td>{shift.cash_desk_branch_name}</Table.Td>
                <Table.Td>{cashDeskLabel(shift.cash_desk_name, shift.cash_desk_code)}</Table.Td>
                <Table.Td>{shift.cashier_name}</Table.Td>
                <Table.Td>{formatDateTime(shift.opened_at)}</Table.Td>
                <Table.Td>{formatDateTime(shift.closed_at)}</Table.Td>
                <Table.Td>
                  <Badge color={shift.status === 'open' ? 'green' : 'gray'} variant="light">
                    {shift.status_display}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap={4} justify="flex-end">
                    {canManage && shift.status === 'open' && (
                      <Tooltip label={t('shifts.closeShift')}>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          onClick={() => void handleForceClose(shift)}
                        >
                          <IconLock size={16} />
                        </ActionIcon>
                      </Tooltip>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))
          )}
        </Table.Tbody>
      </Table>

      {pageCount > 1 && (
        <Group justify="center">
          <Pagination value={page} onChange={setPage} total={pageCount} />
        </Group>
      )}

      {!canManage && (
        <Text size="sm" c="dimmed">
          {t('shifts.forceCloseHint')}
        </Text>
      )}
    </Stack>
  )
}
