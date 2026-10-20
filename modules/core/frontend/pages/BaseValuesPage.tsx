import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconEdit, IconPlus, IconTrash } from '@tabler/icons-react'
import dayjs from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import { useAuth } from '@app/auth/AuthContext'

import * as bankSettingsApi from '../api/bankSettings'
import * as baseValuesApi from '../api/baseValues'
import type { BaseValue } from '../api/baseValues'

const MANAGE_PERMISSION = 'core.base_values.manage'

function formatDate(value: string): string {
  return dayjs(value).format('DD.MM.YYYY')
}

function formatAmount(value: string, currency: string): string {
  return `${value} ${currency}`.trim()
}

export function BaseValuesPage() {
  const { t } = useTranslation('core')
  const { hasPermission } = useAuth()
  const canManage = hasPermission(MANAGE_PERMISSION)

  const [values, setValues] = useState<BaseValue[]>([])
  const [baseCurrency, setBaseCurrency] = useState('')
  const [loading, setLoading] = useState(false)

  const [editing, setEditing] = useState<BaseValue | null>(null)
  const [formOpened, setFormOpened] = useState(false)
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [amount, setAmount] = useState('')
  const [saving, setSaving] = useState(false)

  const notifyError = useCallback(
    (error: unknown) =>
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      }),
    [t],
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [rows, settings] = await Promise.all([
        baseValuesApi.listBaseValues(),
        bankSettingsApi.fetchBankSettings(),
      ])
      setValues(rows)
      setBaseCurrency(settings.base_currency)
    } catch (error) {
      notifyError(error)
    } finally {
      setLoading(false)
    }
  }, [notifyError])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setEffectiveFrom('')
    setAmount('')
    setFormOpened(true)
  }

  const openEdit = (value: BaseValue) => {
    setEditing(value)
    setEffectiveFrom(value.effective_from)
    setAmount(value.amount)
    setFormOpened(true)
  }

  const closeForm = () => setFormOpened(false)

  const save = async () => {
    setSaving(true)
    try {
      const payload = { effective_from: effectiveFrom, amount }
      if (editing) {
        await baseValuesApi.updateBaseValue(editing.id, payload)
        notifications.show({ color: 'green', message: t('baseValues.updated') })
      } else {
        await baseValuesApi.createBaseValue(payload)
        notifications.show({ color: 'green', message: t('baseValues.created') })
      }
      closeForm()
      await load()
    } catch (error) {
      notifyError(error)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (value: BaseValue) => {
    try {
      await baseValuesApi.deleteBaseValue(value.id)
      notifications.show({ color: 'green', message: t('baseValues.deleted') })
      await load()
    } catch (error) {
      notifyError(error)
    }
  }

  const today = dayjs().format('YYYY-MM-DD')
  const isFuture = (value: BaseValue) => value.effective_from > today

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>{t('baseValues.title')}</Title>
        {canManage && (
          <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
            {t('common.add')}
          </Button>
        )}
      </Group>

      <Card withBorder padding="md" radius="md">
        <Text size="sm" c="dimmed">
          {t('baseValues.currencyHint', { currency: baseCurrency || '—' })}
        </Text>
      </Card>

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('baseValues.columns.effectiveFrom')}</Table.Th>
            <Table.Th>{t('baseValues.columns.amount')}</Table.Th>
            <Table.Th>{t('baseValues.columns.status')}</Table.Th>
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
          ) : values.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={4}>
                <Center py="md">
                  <Text c="dimmed">{t('baseValues.empty')}</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            values.map((value) => (
              <Table.Tr key={value.id}>
                <Table.Td>{formatDate(value.effective_from)}</Table.Td>
                <Table.Td>{formatAmount(value.amount, value.currency_code)}</Table.Td>
                <Table.Td>
                  <Badge color={isFuture(value) ? 'blue' : 'teal'} variant="light">
                    {isFuture(value) ? t('baseValues.statusFuture') : t('baseValues.statusActive')}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {canManage && isFuture(value) && (
                    <Group gap={4} justify="flex-end">
                      <Tooltip label={t('common.edit')}>
                        <ActionIcon variant="subtle" onClick={() => openEdit(value)}>
                          <IconEdit size={16} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label={t('common.delete')}>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          onClick={() => void remove(value)}
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

      <Modal
        opened={formOpened}
        onClose={closeForm}
        title={editing ? t('baseValues.editTitle') : t('baseValues.createTitle')}
        size="md"
      >
        <Stack>
          <TextInput
            label={t('baseValues.form.effectiveFrom')}
            type="date"
            value={effectiveFrom}
            onChange={(event) => setEffectiveFrom(event.currentTarget.value)}
            required
          />
          <TextInput
            label={t('baseValues.form.amount', { currency: baseCurrency || '' })}
            placeholder="0.00"
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.currentTarget.value)}
            required
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={closeForm}>
              {t('common.cancel')}
            </Button>
            <Button
              loading={saving}
              disabled={!effectiveFrom || !amount}
              onClick={() => void save()}
            >
              {t('common.save')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
