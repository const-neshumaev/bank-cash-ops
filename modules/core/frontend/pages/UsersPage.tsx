import {
  ActionIcon,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Modal,
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
import { notifications } from '@mantine/notifications'
import {
  IconEdit,
  IconPlus,
  IconSearch,
  IconTrash,
  IconUserCheck,
  IconUserOff,
} from '@tabler/icons-react'
import { useCallback, useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { Role, User } from '@app/api/types'
import { useAuth } from '@app/auth/AuthContext'
import { roleColor } from '@app/roles'

import * as rolesApi from '../api/roles'
import * as usersApi from '../api/users'
import { UserFormModal } from '../components/UserFormModal'

const PAGE_SIZE = 10

const STATUS_OPTIONS = [
  { value: 'true', label: 'Активные' },
  { value: 'false', label: 'Заблокированные' },
]

export function UsersPage() {
  const { user: currentUser } = useAuth()

  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const [search, setSearch] = useState('')
  const [debouncedSearch] = useDebouncedValue(search, 300)
  const [roleFilter, setRoleFilter] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  const [formOpened, setFormOpened] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    void rolesApi
      .listAllRoles()
      .then(setRoles)
      .catch(() => setRoles([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await usersApi.listUsers({
        page,
        pageSize: PAGE_SIZE,
        search: debouncedSearch,
        roles: roleFilter ?? '',
        isActive: statusFilter === null ? '' : statusFilter === 'true',
      })
      setUsers(data.results)
      setTotal(data.count)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [page, debouncedSearch, roleFilter, statusFilter])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setPage(1)
  }, [debouncedSearch, roleFilter, statusFilter])

  const openCreate = () => {
    setEditingUser(null)
    setFormOpened(true)
  }

  const openEdit = (user: User) => {
    setEditingUser(user)
    setFormOpened(true)
  }

  const handleToggleActive = async (user: User) => {
    try {
      if (user.is_active) {
        await usersApi.deactivateUser(user.id)
      } else {
        await usersApi.activateUser(user.id)
      }
      void load()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    }
  }

  const handleDelete = async (permanent: boolean) => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await usersApi.deleteUser(deleteTarget.id, permanent)
      notifications.show({
        color: 'green',
        message: permanent ? 'Пользователь удалён' : 'Пользователь деактивирован',
      })
      setDeleteTarget(null)
      void load()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setDeleting(false)
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Пользователи</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          Добавить
        </Button>
      </Group>

      <Group>
        <TextInput
          placeholder="Поиск по имени, email, телефону"
          leftSection={<IconSearch size={16} />}
          value={search}
          onChange={(event) => setSearch(event.currentTarget.value)}
          w={320}
        />
        <Select
          placeholder="Роль"
          data={roles.map((role) => ({ value: String(role.id), label: role.name }))}
          value={roleFilter}
          onChange={setRoleFilter}
          clearable
          w={220}
        />
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
            <Table.Th>ФИО</Table.Th>
            <Table.Th>Email</Table.Th>
            <Table.Th>Роли</Table.Th>
            <Table.Th>Телефон</Table.Th>
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
          ) : users.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={6}>
                <Center py="md">
                  <Text c="dimmed">Пользователи не найдены</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            users.map((user) => {
              const isSelf = user.id === currentUser?.id
              return (
                <Table.Tr key={user.id}>
                  <Table.Td>{user.full_name || '—'}</Table.Td>
                  <Table.Td>{user.email}</Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      {user.roles.length === 0 ? (
                        <Text c="dimmed" size="sm">
                          —
                        </Text>
                      ) : (
                        user.roles.map((code, index) => (
                          <Badge key={code} color={roleColor(code)} variant="light">
                            {user.roles_display[index] ?? code}
                          </Badge>
                        ))
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>{user.phone || '—'}</Table.Td>
                  <Table.Td>
                    <Badge color={user.is_active ? 'green' : 'gray'} variant="light">
                      {user.is_active ? 'Активен' : 'Заблокирован'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end">
                      <Tooltip label="Редактировать">
                        <ActionIcon variant="subtle" onClick={() => openEdit(user)}>
                          <IconEdit size={16} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label={user.is_active ? 'Заблокировать' : 'Разблокировать'}>
                        <ActionIcon
                          variant="subtle"
                          color={user.is_active ? 'orange' : 'green'}
                          disabled={isSelf}
                          onClick={() => void handleToggleActive(user)}
                        >
                          {user.is_active ? <IconUserOff size={16} /> : <IconUserCheck size={16} />}
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label="Удалить">
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          disabled={isSelf}
                          onClick={() => setDeleteTarget(user)}
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              )
            })
          )}
        </Table.Tbody>
      </Table>

      {pageCount > 1 && (
        <Group justify="center">
          <Pagination value={page} onChange={setPage} total={pageCount} />
        </Group>
      )}

      <UserFormModal
        opened={formOpened}
        user={editingUser}
        onClose={() => setFormOpened(false)}
        onSaved={() => void load()}
      />

      <Modal
        opened={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Удаление пользователя"
      >
        <Stack>
          <Text>
            Пользователь <b>{deleteTarget?.full_name || deleteTarget?.email}</b> будет деактивирован.
            Запись сохраняется для аудита.
          </Text>
          <Group justify="space-between">
            <Button
              variant="default"
              color="red"
              loading={deleting}
              onClick={() => void handleDelete(true)}
            >
              Удалить навсегда
            </Button>
            <Group>
              <Button variant="default" onClick={() => setDeleteTarget(null)}>
                Отмена
              </Button>
              <Button color="orange" loading={deleting} onClick={() => void handleDelete(false)}>
                Деактивировать
              </Button>
            </Group>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
