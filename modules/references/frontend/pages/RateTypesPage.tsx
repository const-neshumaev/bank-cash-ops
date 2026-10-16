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
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconEdit, IconPlus, IconTrash } from '@tabler/icons-react'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'

import * as rateTypesApi from '../api/rateTypes'
import { RateTypeFormModal } from '../components/RateTypeFormModal'

const PRINCIPLE_COLORS: Record<rateTypesApi.RatePrinciple, string> = {
  official: 'blue',
  buy: 'teal',
  sell: 'grape',
  conversion: 'orange',
}

export function RateTypesPage() {
  const { t } = useTranslation('references')
  const [rateTypes, setRateTypes] = useState<rateTypesApi.RateType[]>([])
  const [loading, setLoading] = useState(false)

  const [formOpened, setFormOpened] = useState(false)
  const [editing, setEditing] = useState<rateTypesApi.RateType | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRateTypes(await rateTypesApi.listRateTypes())
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setFormOpened(true)
  }

  const openEdit = (rateType: rateTypesApi.RateType) => {
    setEditing(rateType)
    setFormOpened(true)
  }

  const handleDelete = async (rateType: rateTypesApi.RateType) => {
    try {
      await rateTypesApi.deleteRateType(rateType.id)
      notifications.show({ color: 'green', message: t('rateTypes.deleted') })
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
        <Title order={3}>{t('rateTypes.title')}</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          {t('common.add')}
        </Button>
      </Group>

      <Text size="sm" c="dimmed">
        {t('rateTypes.hint')}
      </Text>

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('rateTypes.columns.name')}</Table.Th>
            <Table.Th>{t('rateTypes.columns.code')}</Table.Th>
            <Table.Th>{t('rateTypes.columns.principle')}</Table.Th>
            <Table.Th>{t('rateTypes.columns.status')}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {loading ? (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Center py="md">
                  <Loader size="sm" />
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : rateTypes.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Center py="md">
                  <Text c="dimmed">{t('rateTypes.empty')}</Text>
                </Center>
              </Table.Td>
            </Table.Tr>
          ) : (
            rateTypes.map((rateType) => (
              <Table.Tr key={rateType.id}>
                <Table.Td>
                  <Group gap={6}>
                    <Text fw={500}>{rateType.name}</Text>
                    {rateType.is_system && (
                      <Badge color="gray" variant="light">
                        {t('rateTypes.system')}
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>{rateType.code}</Table.Td>
                <Table.Td>
                  <Badge color={PRINCIPLE_COLORS[rateType.principle]} variant="light">
                    {t(`rateTypes.principle.${rateType.principle}`)}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Badge color={rateType.is_active ? 'teal' : 'gray'} variant="light">
                    {rateType.is_active ? t('rateTypes.active') : t('rateTypes.inactive')}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap={4} justify="flex-end">
                    <Tooltip label={t('common.edit')}>
                      <ActionIcon variant="subtle" onClick={() => openEdit(rateType)}>
                        <IconEdit size={16} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip
                      label={
                        rateType.is_system ? t('rateTypes.systemDeleteHint') : t('common.delete')
                      }
                    >
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        disabled={rateType.is_system}
                        onClick={() => void handleDelete(rateType)}
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

      <RateTypeFormModal
        opened={formOpened}
        rateType={editing}
        onClose={() => setFormOpened(false)}
        onSaved={() => void load()}
      />
    </Stack>
  )
}
