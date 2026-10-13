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
import { useDebouncedValue } from '@mantine/hooks'
import dayjs from 'dayjs'
import { notifications } from '@mantine/notifications'
import { useCallback, useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { BranchOption, CashDeskOption, Shift } from '@app/api/types'

import * as branchesApi from '../api/branches'
import * as cashDesksApi from '../api/cashDesks'
import * as shiftsApi from '../api/shifts'

function branchLabel(branch: BranchOption): string {
  return branch.code ? `${branch.name} (${branch.code})` : branch.name
}

function cashDeskLabel(cashDesk: CashDeskOption): string {
  return cashDesk.code ? `${cashDesk.name} (${cashDesk.code})` : cashDesk.name
}

export function WorkplacePage() {
  const [shift, setShift] = useState<Shift | null>(null)
  const [branches, setBranches] = useState<BranchOption[]>([])
  const [cashDesks, setCashDesks] = useState<CashDeskOption[]>([])
  const [selectedBranch, setSelectedBranch] = useState<string | null>(null)
  const [selectedDesk, setSelectedDesk] = useState<string | null>(null)
  const [branchSearch, setBranchSearch] = useState('')
  const [deskSearch, setDeskSearch] = useState('')
  const [debouncedBranchSearch] = useDebouncedValue(branchSearch, 300)
  const [debouncedDeskSearch] = useDebouncedValue(deskSearch, 300)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const loadCurrent = useCallback(async () => {
    setLoading(true)
    try {
      setShift(await shiftsApi.fetchCurrentShift())
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCurrent()
  }, [loadCurrent])

  useEffect(() => {
    void branchesApi
      .listSelectableBranches(debouncedBranchSearch)
      .then(setBranches)
      .catch((error) => {
        notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
      })
  }, [debouncedBranchSearch])

  useEffect(() => {
    if (!selectedBranch) {
      setCashDesks([])
      return
    }
    void cashDesksApi
      .listSelectableCashDesks(Number(selectedBranch), debouncedDeskSearch)
      .then(setCashDesks)
      .catch((error) => {
        notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
      })
  }, [selectedBranch, debouncedDeskSearch])

  const handleOpen = async () => {
    if (!selectedDesk) return
    setSubmitting(true)
    try {
      await shiftsApi.openShift(Number(selectedDesk))
      notifications.show({ color: 'green', message: 'Смена открыта' })
      setSelectedBranch(null)
      setSelectedDesk(null)
      await loadCurrent()
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
      await loadCurrent()
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
                Отделение:
              </Text>
              <Text size="sm">{shift.cash_desk_branch_name}</Text>
            </Group>
            <Group>
              <Text size="sm" c="dimmed">
                Касса:
              </Text>
              <Text size="sm">
                {shift.cash_desk_code
                  ? `${shift.cash_desk_name} (${shift.cash_desk_code})`
                  : shift.cash_desk_name}
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
              Выберите отделение и кассу, затем откройте смену, чтобы начать работу.
            </Text>
            <Select
              label="Отделение"
              placeholder="Выберите отделение"
              data={branches.map((branch) => ({
                value: String(branch.id),
                label: branchLabel(branch),
              }))}
              searchable
              searchValue={branchSearch}
              onSearchChange={setBranchSearch}
              value={selectedBranch}
              onChange={(value) => {
                setSelectedBranch(value)
                setSelectedDesk(null)
              }}
              nothingFoundMessage="Отделения не найдены"
            />
            <Select
              label="Касса"
              placeholder={selectedBranch ? 'Выберите кассу' : 'Сначала выберите отделение'}
              data={cashDesks.map((desk) => ({
                value: String(desk.id),
                label: cashDeskLabel(desk),
              }))}
              searchable
              searchValue={deskSearch}
              onSearchChange={setDeskSearch}
              value={selectedDesk}
              onChange={setSelectedDesk}
              disabled={!selectedBranch}
              nothingFoundMessage="Кассы не найдены"
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
