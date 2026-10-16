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
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import type { Permission, Role } from '@app/api/types'

import * as rolesApi from '../api/roles'
import { RoleFormModal } from '../components/RoleFormModal'

export function RolesPage() {
  const { t } = useTranslation('core')
  const [roles, setRoles] = useState<Role[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [debouncedSearch] = useDebouncedValue(search, 300)

  const [formOpened, setFormOpened] = useState(false)
  const [editingRole, setEditingRole] = useState<Role | null>(null)

  useEffect(() => {
    void rolesApi
      .listPermissions()
      .then(setPermissions)
      .catch(() => setPermissions([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await rolesApi.listRoles({ search: debouncedSearch, pageSize: 100 })
      setRoles(data.results)
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch])

  useEffect(() => {
    void load()
  }, [load])

  const permissionName = (code: string) =>
    permissions.find((permission) => permission.code === code)?.name ?? code

  const openCreate = () => {
    setEditingRole(null)
    setFormOpened(true)
  }

  const openEdit = (role: Role) => {
    setEditingRole(role)
    setFormOpened(true)
  }

  const handleDelete = async (role: Role) => {
    try {
      await rolesApi.deleteRole(role.id)
      notifications.show({ color: 'green', message: t('roles.deleted') })
      void load()
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
    }
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>{t('roles.title')}</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          {t('common.add')}
        </Button>
      </Group>

      <TextInput
        placeholder={t('roles.searchPlaceholder')}
        leftSection={<IconSearch size={16} />}
        value={search}
        onChange={(event) => setSearch(event.currentTarget.value)}
        w={320}
      />

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('roles.columns.name')}</Table.Th>
            <Table.Th>{t('roles.columns.permissions')}</Table.Th>
            <Table.Th>{t('roles.columns.users')}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {loading ? (
            <Table.Tr>
              <Table.Td colSpan={4}>
                <Center py="md">
                  <Loader size="sm" />
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : roles.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={4}>
                <Center py="md">
                  <Text c="dimmed">{t('roles.empty')}</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            roles.map((role) => (
              <Table.Tr key={role.id}>
                <Table.Td>
                  <Group gap={6}>
                    <Text fw={500}>{role.name}</Text>
                    {role.is_system && (
                      <Badge color="gray" variant="light">
                        {t('roles.system')}
                      </Badge>
                    )}
                  </Group>
                  {role.description && (
                    <Text size="xs" c="dimmed">
                      {role.description}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {role.permissions.length === 0 ? (
                    <Text c="dimmed" size="sm">
                      —
                    </Text>
                  ) : (
                    <Group gap={4}>
                      {role.permissions.map((code) => (
                        <Badge key={code} variant="light">
                          {permissionName(code)}
                        </Badge>
                      ))}
                    </Group>
                  )}
                </Table.Td>
                <Table.Td>{role.users_count}</Table.Td>
                <Table.Td>
                  <Group gap={4} justify="flex-end">
                    <Tooltip label={t('common.edit')}>
                      <ActionIcon variant="subtle" onClick={() => openEdit(role)}>
                        <IconEdit size={16} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip label={role.is_system ? t('roles.systemDeleteHint') : t('common.delete')}>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        disabled={role.is_system}
                        onClick={() => void handleDelete(role)}
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

      <RoleFormModal
        opened={formOpened}
        role={editingRole}
        onClose={() => setFormOpened(false)}
        onSaved={() => void load()}
      />
    </Stack>
  )
}
