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
  Title,
  Tooltip,
} from '@mantine/core'
import dayjs from 'dayjs'
import { notifications } from '@mantine/notifications'
import { IconLock } from '@tabler/icons-react'
import { useCallback, useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { Shift } from '@app/api/types'
import { useAuth } from '@app/auth/AuthContext'

import * as shiftsApi from '../api/shifts'

const PAGE_SIZE = 20

const STATUS_OPTIONS = [
  { value: 'open', label: 'Открытые' },
  { value: 'closed', label: 'Закрытые' },
]

function formatDateTime(value: string | null): string {
  return value ? dayjs(value).format('DD.MM.YYYY HH:mm') : '—'
}

export function ShiftsPage() {
  const { hasPermission } = useAuth()
  const canManage = hasPermission('core.shifts.manage')

  const [shifts, setShifts] = useState<Shift[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await shiftsApi.listShifts({
        page,
        pageSize: PAGE_SIZE,
        status: statusFilter ?? '',
      })
      setShifts(data.results)
      setTotal(data.count)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setPage(1)
  }, [statusFilter])

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
        <Select
          placeholder="Статус"
          data={STATUS_OPTIONS}
          value={statusFilter}
          onChange={setStatusFilter}
          clearable
          w={200}
        />
      </Group>

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
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
              <Table.Td colSpan={6}>
                <Center py="md">
                  <Loader size="sm" />
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : shifts.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={6}>
                <Center py="md">
                  <Text c="dimmed">Смены не найдены</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            shifts.map((shift) => (
              <Table.Tr key={shift.id}>
                <Table.Td>
                  {shift.cash_desk_name} ({shift.cash_desk_code})
                </Table.Td>
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
