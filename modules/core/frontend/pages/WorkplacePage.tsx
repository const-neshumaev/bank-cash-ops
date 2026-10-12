import {
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import dayjs from 'dayjs'
import { notifications } from '@mantine/notifications'
import { useCallback, useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { CashDesk, Shift } from '@app/api/types'

import * as cashDesksApi from '../api/cashDesks'
import * as shiftsApi from '../api/shifts'

export function WorkplacePage() {
  const [shift, setShift] = useState<Shift | null>(null)
  const [cashDesks, setCashDesks] = useState<CashDesk[]>([])
  const [selectedDesk, setSelectedDesk] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [current, desks] = await Promise.all([
        shiftsApi.fetchCurrentShift(),
        cashDesksApi.listAllCashDesks(),
      ])
      setShift(current)
      setCashDesks(desks.filter((desk) => desk.is_active))
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleOpen = async () => {
    if (!selectedDesk) return
    setSubmitting(true)
    try {
      await shiftsApi.openShift(Number(selectedDesk))
      notifications.show({ color: 'green', message: 'Смена открыта' })
      await load()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = async () => {
    if (!shift) return
    setSubmitting(true)
    try {
      await shiftsApi.closeShift(shift.id)
      notifications.show({ color: 'green', message: 'Смена закрыта' })
      await load()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }

  return (
    <Stack maw={640}>
      <Title order={3}>Рабочее место кассира</Title>

      {shift ? (
        <Card withBorder padding="lg" radius="md">
          <Stack>
            <Group justify="space-between">
              <Text fw={500}>Открытая смена</Text>
              <Badge color="green" variant="light">
                {shift.status_display}
              </Badge>
            </Group>
            <Group>
              <Text size="sm" c="dimmed">
                Касса:
              </Text>
              <Text size="sm">
                {shift.cash_desk_name} ({shift.cash_desk_code})
              </Text>
            </Group>
            <Group>
              <Text size="sm" c="dimmed">
                Открыта:
              </Text>
              <Text size="sm">{dayjs(shift.opened_at).format('DD.MM.YYYY HH:mm')}</Text>
            </Group>
            <Text size="sm" c="dimmed">
              Смена привязана к выбранной кассе и сохраняется на сервере, пока вы её не закроете.
            </Text>
            <Group justify="flex-end">
              <Button color="red" loading={submitting} onClick={() => void handleClose()}>
                Закрыть смену
              </Button>
            </Group>
          </Stack>
        </Card>
      ) : (
        <Card withBorder padding="lg" radius="md">
          <Stack>
            <Text fw={500}>Смена не открыта</Text>
            <Text size="sm" c="dimmed">
              Выберите кассу и откройте смену, чтобы начать работу.
            </Text>
            <Select
              label="Касса"
              placeholder="Выберите кассу"
              data={cashDesks.map((desk) => ({
                value: String(desk.id),
                label: `${desk.name} (${desk.code})`,
              }))}
              value={selectedDesk}
              onChange={setSelectedDesk}
              searchable
            />
            <Group justify="flex-end">
              <Button
                disabled={!selectedDesk}
                loading={submitting}
                onClick={() => void handleOpen()}
              >
                Открыть смену
              </Button>
            </Group>
          </Stack>
        </Card>
      )}
    </Stack>
  )
}
