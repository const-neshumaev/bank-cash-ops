import {
  ActionIcon,
  Badge,
  Button,
  Center,
  Group,
  Loader,
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
import type { Branch } from '@app/api/types'

import * as branchesApi from '../api/branches'
import { BranchFormModal } from '../components/BranchFormModal'

export function BranchesPage() {
  const [branches, setBranches] = useState<Branch[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [debouncedSearch] = useDebouncedValue(search, 300)

  const [formOpened, setFormOpened] = useState(false)
  const [editingBranch, setEditingBranch] = useState<Branch | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await branchesApi.listBranches({ search: debouncedSearch, pageSize: 100 })
      setBranches(data.results)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditingBranch(null)
    setFormOpened(true)
  }

  const openEdit = (branch: Branch) => {
    setEditingBranch(branch)
    setFormOpened(true)
  }

  const handleDelete = async (branch: Branch) => {
    try {
      await branchesApi.deleteBranch(branch.id)
      notifications.show({ color: 'green', message: 'Отделение удалено' })
      void load()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    }
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Отделения банка</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          Добавить
        </Button>
      </Group>

      <TextInput
        placeholder="Поиск по названию, коду, адресу"
        leftSection={<IconSearch size={16} />}
        value={search}
        onChange={(event) => setSearch(event.currentTarget.value)}
        w={320}
      />

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Название</Table.Th>
            <Table.Th>Код</Table.Th>
            <Table.Th>Вышестоящее</Table.Th>
            <Table.Th>Адрес</Table.Th>
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
          ) : branches.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={6}>
                <Center py="md">
                  <Text c="dimmed">Отделения не найдены</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            branches.map((branch) => (
              <Table.Tr key={branch.id}>
                <Table.Td>
                  <Group gap={6}>
                    <Text>{branch.name}</Text>
                    {branch.is_head_office && (
                      <Badge color="blue" variant="light">
                        головной офис
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>{branch.code || '—'}</Table.Td>
                <Table.Td>{branch.parent_name || '—'}</Table.Td>
                <Table.Td>{branch.address || '—'}</Table.Td>
                <Table.Td>
                  <Badge color={branch.is_active ? 'green' : 'gray'} variant="light">
                    {branch.is_active ? 'Активно' : 'Отключено'}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap={4} justify="flex-end">
                    <Tooltip label="Редактировать">
                      <ActionIcon variant="subtle" onClick={() => openEdit(branch)}>
                        <IconEdit size={16} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip label="Удалить">
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        onClick={() => void handleDelete(branch)}
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

      <BranchFormModal
        opened={formOpened}
        branch={editingBranch}
        onClose={() => setFormOpened(false)}
        onSaved={() => void load()}
      />
    </Stack>
  )
}
