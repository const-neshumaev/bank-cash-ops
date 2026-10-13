import {
  ActionIcon,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconEdit, IconPlus, IconSearch, IconTrash } from '@tabler/icons-react'
import { useCallback, useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { Branch, CashDesk } from '@app/api/types'

import * as branchesApi from '../api/branches'
import * as cashDesksApi from '../api/cashDesks'
import { CashDeskFormModal } from '../components/CashDeskFormModal'

export function CashDesksPage() {
  const [cashDesks, setCashDesks] = useState<CashDesk[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [debouncedSearch] = useDebouncedValue(search, 300)
  const [branchFilter, setBranchFilter] = useState<string | null>(null)

  const [formOpened, setFormOpened] = useState(false)
  const [editingCashDesk, setEditingCashDesk] = useState<CashDesk | null>(null)

  useEffect(() => {
    void branchesApi
      .listAllBranches()
      .then(setBranches)
      .catch(() => setBranches([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await cashDesksApi.listCashDesks({
        search: debouncedSearch,
        pageSize: 100,
        branch: branchFilter ? Number(branchFilter) : '',
      })
      setCashDesks(data.results)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, branchFilter])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditingCashDesk(null)
    setFormOpened(true)
  }

  const openEdit = (cashDesk: CashDesk) => {
    setEditingCashDesk(cashDesk)
    setFormOpened(true)
  }

  const handleDelete = async (cashDesk: CashDesk) => {
    try {
      await cashDesksApi.deleteCashDesk(cashDesk.id)
      notifications.show({ color: 'green', message: 'Касса удалена' })
      void load()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    }
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Кассы</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          Добавить
        </Button>
      </Group>

      <Group>
        <TextInput
          placeholder="Поиск по названию, коду, MAC-адресу"
          leftSection={<IconSearch size={16} />}
          value={search}
          onChange={(event) => setSearch(event.currentTarget.value)}
          w={320}
        />
        <Select
          placeholder="Отделение"
          data={branches.map((branch) => ({ value: String(branch.id), label: branch.name }))}
          value={branchFilter}
          onChange={setBranchFilter}
          clearable
          w={240}
        />
      </Group>

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Название</Table.Th>
            <Table.Th>Код</Table.Th>
            <Table.Th>Отделение</Table.Th>
            <Table.Th>MAC-адрес</Table.Th>
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
          ) : cashDesks.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={6}>
                <Center py="md">
                  <Text c="dimmed">Кассы не найдены</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            cashDesks.map((cashDesk) => (
              <Table.Tr key={cashDesk.id}>
                <Table.Td>{cashDesk.name}</Table.Td>
                <Table.Td>{cashDesk.code || '—'}</Table.Td>
                <Table.Td>{cashDesk.branch_name}</Table.Td>
                <Table.Td>{cashDesk.mac_address || '—'}</Table.Td>
                <Table.Td>
                  <Badge color={cashDesk.is_active ? 'green' : 'gray'} variant="light">
                    {cashDesk.is_active ? 'Активна' : 'Отключена'}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap={4} justify="flex-end">
                    <Tooltip label="Редактировать">
                      <ActionIcon variant="subtle" onClick={() => openEdit(cashDesk)}>
                        <IconEdit size={16} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip label="Удалить">
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        onClick={() => void handleDelete(cashDesk)}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))
          )}
        </Table.Tbody>
      </Table>

      <CashDeskFormModal
        opened={formOpened}
        cashDesk={editingCashDesk}
        onClose={() => setFormOpened(false)}
        onSaved={() => void load()}
      />
    </Stack>
  )
}
