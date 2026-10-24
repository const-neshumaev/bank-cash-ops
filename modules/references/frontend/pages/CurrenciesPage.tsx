import {
  ActionIcon,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Stack,
  Switch,
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
import { useAuth } from '@app/auth/AuthContext'

import * as currenciesApi from '../api/currencies'
import { CurrencyFormModal } from '../components/CurrencyFormModal'

const MANAGE_PERMISSION = 'references.manage'

export function CurrenciesPage() {
  const { t } = useTranslation('references')
  const { hasPermission } = useAuth()
  const canManage = hasPermission(MANAGE_PERMISSION)
  const [currencies, setCurrencies] = useState<currenciesApi.Currency[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [debouncedSearch] = useDebouncedValue(search, 300)
  const [activeOnly, setActiveOnly] = useState(false)

  const [formOpened, setFormOpened] = useState(false)
  const [editing, setEditing] = useState<currenciesApi.Currency | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await currenciesApi.listCurrencies({
        search: debouncedSearch,
        pageSize: 100,
        isActive: activeOnly ? true : undefined,
      })
      setCurrencies(data.results)
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, activeOnly])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setFormOpened(true)
  }

  const openEdit = (currency: currenciesApi.Currency) => {
    setEditing(currency)
    setFormOpened(true)
  }

  const handleDelete = async (currency: currenciesApi.Currency) => {
    try {
      await currenciesApi.deleteCurrency(currency.code)
      notifications.show({ color: 'green', message: t('currencies.deleted') })
      void load()
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    }
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>{t('currencies.title')}</Title>
        {canManage && (
          <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
            {t('common.add')}
          </Button>
        )}
      </Group>

      <Group>
        <TextInput
          placeholder={t('currencies.searchPlaceholder')}
          leftSection={<IconSearch size={16} />}
          value={search}
          onChange={(event) => setSearch(event.currentTarget.value)}
          w={320}
        />
        <Switch
          label={t('currencies.activeOnly')}
          checked={activeOnly}
          onChange={(event) => setActiveOnly(event.currentTarget.checked)}
        />
      </Group>

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('currencies.columns.code')}</Table.Th>
            <Table.Th>{t('currencies.columns.numericCode')}</Table.Th>
            <Table.Th>{t('currencies.columns.name')}</Table.Th>
            <Table.Th>{t('currencies.columns.symbol')}</Table.Th>
            <Table.Th>{t('currencies.columns.minorUnits')}</Table.Th>
            <Table.Th>{t('currencies.columns.status')}</Table.Th>
            <Table.Th />
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
          ) : currencies.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={7}>
                <Center py="md">
                  <Text c="dimmed">{t('currencies.empty')}</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            currencies.map((currency) => (
              <Table.Tr key={currency.code}>
                <Table.Td>
                  <Text fw={500}>{currency.code}</Text>
                </Table.Td>
                <Table.Td>{currency.numeric_code || '—'}</Table.Td>
                <Table.Td>{currency.name}</Table.Td>
                <Table.Td>{currency.symbol || '—'}</Table.Td>
                <Table.Td>{currency.minor_units}</Table.Td>
                <Table.Td>
                  <Badge color={currency.is_active ? 'teal' : 'gray'} variant="light">
                    {currency.is_active ? t('currencies.active') : t('currencies.inactive')}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {canManage && (
                    <Group gap={4} justify="flex-end">
                      <Tooltip label={t('common.edit')}>
                        <ActionIcon variant="subtle" onClick={() => openEdit(currency)}>
                          <IconEdit size={16} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label={t('common.delete')}>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          onClick={() => void handleDelete(currency)}
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  )}
                </Table.Td>
              </Table.Tr>
            ))
          )}
        </Table.Tbody>
      </Table>

      <CurrencyFormModal
        opened={formOpened}
        currency={editing}
        onClose={() => setFormOpened(false)}
        onSaved={() => void load()}
      />
    </Stack>
  )
}
