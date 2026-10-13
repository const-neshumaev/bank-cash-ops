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

import { extractErrorMessage } from '@app/api/errors'
import type { BranchOption, CashDeskOption, Shift } from '@app/api/types'
import { useAuth } from '@app/auth/AuthContext'

import * as branchesApi from '../api/branches'
import * as cashDesksApi from '../api/cashDesks'
import * as shiftsApi from '../api/shifts'

const PAGE_SIZE = 20

const STATUS_OPTIONS = [
  { value: 'open', label: 'Открытые' },
  { value: 'closed', label: 'Закрытые' },
]

type PeriodValue = '7' | '30' | '90' | 'all' | 'custom'

const PERIOD_OPTIONS = [
  { value: '7', label: 'Последние 7 дней' },
  { value: '30', label: 'Последние 30 дней' },
  { value: '90', label: 'Последние 90 дней' },
  { value: 'all', label: 'Всё время' },
  { value: 'custom', label: 'Произвольный период' },
]

const COLUMN_COUNT = 7

function formatDateTime(value: string | null): string {
  return value ? dayjs(value).format('DD.MM.YYYY HH:mm') : '—'
}

function cashDeskLabel(name: string, code: string | null): string {
  return code ? `${name} (${code})` : name
}

export function ShiftsPage() {
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
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
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
      notifications.show({ color: 'green', message: 'Смена закрыта' })
      void load()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Кассовые смены</Title>
      </Group>

      <Group align="flex-end">
        <Select
          label="Период"
          data={PERIOD_OPTIONS}
          value={period}
          onChange={(value) => setPeriod((value as PeriodValue) ?? '30')}
          w={200}
        />
        {period === 'custom' && (
          <>
            <TextInput
              type="date"
              label="С"
              value={customFrom}
              onChange={(event) => setCustomFrom(event.currentTarget.value)}
              w={160}
            />
            <TextInput
              type="date"
              label="По"
              value={customTo}
              onChange={(event) => setCustomTo(event.currentTarget.value)}
              w={160}
            />
          </>
        )}
        <Select
          label="Статус"
          placeholder="Любой"
          data={STATUS_OPTIONS}
          value={statusFilter}
          onChange={setStatusFilter}
          clearable
          w={160}
        />
        <Select
          label="Отделение"
          placeholder="Все отделения"
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
          label="Касса"
          placeholder={branchFilter ? 'Все кассы' : 'Сначала выберите отделение'}
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
            <Table.Th>Отделение</Table.Th>
            <Table.Th>Касса</Table.Th>
            <Table.Th>Кассир</Table.Th>
            <Table.Th>Открыта</Table.Th>
            <Table.Th>Закрыта</Table.Th>
            <Table.Th>Статус</Table.Th>
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
                  <Text c="dimmed">Смены не найдены</Text>
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
                      <Tooltip label="Закрыть смену">
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
          Принудительное закрытие чужих смен доступно администраторам и заведующим отделениями.
        </Text>
      )}
    </Stack>
  )
}
