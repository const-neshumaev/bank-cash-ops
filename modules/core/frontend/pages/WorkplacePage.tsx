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
import { useTranslation } from 'react-i18next'

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
  const { t } = useTranslation('core')
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
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
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
        notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
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
        notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
      })
  }, [selectedBranch, debouncedDeskSearch])

  const handleOpen = async () => {
    if (!selectedDesk) return
    setSubmitting(true)
    try {
      await shiftsApi.openShift(Number(selectedDesk))
      notifications.show({ color: 'green', message: t('workplace.openedMessage') })
      setSelectedBranch(null)
      setSelectedDesk(null)
      await loadCurrent()
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = async () => {
    if (!shift) return
    setSubmitting(true)
    try {
      await shiftsApi.closeShift(shift.id)
      notifications.show({ color: 'green', message: t('workplace.closedMessage') })
      await loadCurrent()
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
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
      <Title order={3}>{t('workplace.title')}</Title>

      {shift ? (
        <Card withBorder padding="lg" radius="md">
          <Stack>
            <Group justify="space-between">
              <Text fw={500}>{t('workplace.openShift')}</Text>
              <Badge color="green" variant="light">
                {shift.status_display}
              </Badge>
            </Group>
            <Group>
              <Text size="sm" c="dimmed">
                {t('workplace.branch')}
              </Text>
              <Text size="sm">{shift.cash_desk_branch_name}</Text>
            </Group>
            <Group>
              <Text size="sm" c="dimmed">
                {t('workplace.cashDesk')}
              </Text>
              <Text size="sm">
                {shift.cash_desk_code
                  ? `${shift.cash_desk_name} (${shift.cash_desk_code})`
                  : shift.cash_desk_name}
              </Text>
            </Group>
            <Group>
              <Text size="sm" c="dimmed">
                {t('workplace.openedAt')}
              </Text>
              <Text size="sm">{dayjs(shift.opened_at).format('DD.MM.YYYY HH:mm')}</Text>
            </Group>
            <Text size="sm" c="dimmed">
              {t('workplace.shiftBoundHint')}
            </Text>
            <Group justify="flex-end">
              <Button color="red" loading={submitting} onClick={() => void handleClose()}>
                {t('workplace.closeShift')}
              </Button>
            </Group>
          </Stack>
        </Card>
      ) : (
        <Card withBorder padding="lg" radius="md">
          <Stack>
            <Text fw={500}>{t('workplace.noShift')}</Text>
            <Text size="sm" c="dimmed">
              {t('workplace.noShiftHint')}
            </Text>
            <Select
              label={t('workplace.branchLabel')}
              placeholder={t('workplace.selectBranch')}
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
              nothingFoundMessage={t('workplace.noBranchesFound')}
            />
            <Select
              label={t('workplace.cashDeskLabel')}
              placeholder={selectedBranch ? t('workplace.selectCashDesk') : t('workplace.selectBranchFirst')}
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
              nothingFoundMessage={t('workplace.noCashDesksFound')}
            />
            <Group justify="flex-end">
              <Button
                disabled={!selectedDesk}
                loading={submitting}
                onClick={() => void handleOpen()}
              >
                {t('workplace.openShiftButton')}
              </Button>
            </Group>
          </Stack>
        </Card>
      )}
    </Stack>
  )
}
