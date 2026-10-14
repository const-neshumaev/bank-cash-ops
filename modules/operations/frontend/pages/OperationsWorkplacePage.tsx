import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle } from '@tabler/icons-react'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { NavLink as RouterNavLink } from 'react-router-dom'

import { extractErrorMessage } from '@app/api/errors'
import { useAuth } from '@app/auth/AuthContext'

import * as operationsApi from '../api/operations'
import type { Currency, Operation, WorkplaceContext, WorkplaceOperation } from '../api/operations'

function currencyLabel(code: string, currencies: Currency[]): string {
  const currency = currencies.find((item) => item.code === code)
  return currency ? `${currency.code} — ${currency.name}` : code
}

const RATE_TYPE_LABELS: Record<string, string> = {
  buy: 'покупка',
  sell: 'продажа',
  central: 'учётный',
}

function rateTypeLabel(rateType: string): string {
  return RATE_TYPE_LABELS[rateType] ?? rateType
}

function amountsText(operation: Operation): string {
  return operation.lines.map((line) => `${line.amount} ${line.currency}`).join(', ')
}

export function OperationsWorkplacePage() {
  const { hasPermission } = useAuth()
  const [context, setContext] = useState<WorkplaceContext | null>(null)
  const [journal, setJournal] = useState<Operation[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const [operationCode, setOperationCode] = useState<string | null>(null)
  const [amounts, setAmounts] = useState<Record<string, string>>({})
  const [slotCurrencies, setSlotCurrencies] = useState<Record<string, string>>({})
  const [clientName, setClientName] = useState('')
  const [clientDocument, setClientDocument] = useState('')
  const [comment, setComment] = useState('')

  const selectedOperation = useMemo<WorkplaceOperation | undefined>(
    () => context?.operations.find((item) => item.code === operationCode),
    [context, operationCode],
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await operationsApi.fetchWorkplace()
      setContext(data)
      setJournal(data.cash_desk_id === null ? [] : await operationsApi.listOperations(data.cash_desk_id))
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    // Reset the form whenever another operation type is chosen.
    setAmounts({})
    setSlotCurrencies({})
    setClientName('')
    setClientDocument('')
    setComment('')
  }, [operationCode])

  const handleSubmit = async () => {
    if (!selectedOperation) return
    const lines = selectedOperation.slots.map((slot) => ({
      slot: slot.code,
      currency: slot.fixed_currency || slotCurrencies[slot.code] || '',
      amount: amounts[slot.code] ?? '',
      rate: null,
    }))
    if (lines.some((line) => !line.currency || Number(line.amount) <= 0)) {
      notifications.show({ color: 'red', title: 'Ошибка', message: 'Заполните суммы и валюты' })
      return
    }
    setSubmitting(true)
    try {
      await operationsApi.postOperation({
        operation_type: selectedOperation.code,
        lines,
        client_name: clientName,
        client_document: clientDocument,
        comment,
        idempotency_key: crypto.randomUUID(),
      })
      notifications.show({ color: 'green', message: 'Операция проведена' })
      setOperationCode(null)
      await load()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setSubmitting(false)
    }
  }

  const handleReverse = async (id: number) => {
    setSubmitting(true)
    try {
      await operationsApi.reverseOperation(id)
      notifications.show({ color: 'green', message: 'Операция сторнирована' })
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

  if (!context || context.shift_id === null) {
    return (
      <Stack maw={640}>
        <Title order={3}>Касса</Title>
        <Alert color="yellow" icon={<IconAlertCircle size={16} />} title="Смена не открыта">
          <Stack gap="sm" align="flex-start">
            <Text size="sm">Чтобы выполнять операции, откройте кассовую смену.</Text>
            <Button component={RouterNavLink} to="/workplace" variant="light">
              Открыть смену
            </Button>
          </Stack>
        </Alert>
      </Stack>
    )
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Касса</Title>
        <Badge variant="light">Смена #{context.shift_id}</Badge>
      </Group>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Text fw={500}>Остатки наличных</Text>
          {context.balances.length === 0 ? (
            <Text size="sm" c="dimmed">
              Остатков пока нет.
            </Text>
          ) : (
            <Group gap="xl">
              {context.balances.map((balance) => (
                <Text key={balance.currency} size="sm">
                  <b>{balance.amount}</b> {balance.currency}
                </Text>
              ))}
            </Group>
          )}
        </Stack>
      </Card>

      {context.rates.length > 0 && (
        <Card withBorder padding="lg" radius="md">
          <Stack gap="xs">
            <Text fw={500}>Курсы валют</Text>
            <Group gap="xl">
              {context.rates.map((rate) => (
                <Text key={`${rate.currency}-${rate.base_currency}-${rate.rate_type}`} size="sm">
                  1 {rate.currency} = <b>{rate.value}</b> {rate.base_currency} (
                  {rateTypeLabel(rate.rate_type)})
                </Text>
              ))}
            </Group>
          </Stack>
        </Card>
      )}

      <Card withBorder padding="lg" radius="md">
        <Stack>
          <Text fw={500}>Новая операция</Text>
          <Select
            label="Операция"
            placeholder="Выберите операцию"
            data={context.operations.map((item) => ({ value: item.code, label: item.name }))}
            value={operationCode}
            onChange={setOperationCode}
            searchable
            nothingFoundMessage="Операции не найдены"
          />

          {selectedOperation && (
            <>
              {selectedOperation.slots.map((slot) => (
                <Group key={slot.code} align="flex-end" grow>
                  <TextInput
                    label={slot.name}
                    placeholder="0.00"
                    inputMode="decimal"
                    value={amounts[slot.code] ?? ''}
                    onChange={(event) =>
                      setAmounts((prev) => ({ ...prev, [slot.code]: event.currentTarget.value }))
                    }
                  />
                  <Select
                    label="Валюта"
                    data={context.currencies.map((currency) => ({
                      value: currency.code,
                      label: currencyLabel(currency.code, context.currencies),
                    }))}
                    value={slot.fixed_currency || slotCurrencies[slot.code] || null}
                    onChange={(value) =>
                      setSlotCurrencies((prev) => ({ ...prev, [slot.code]: value ?? '' }))
                    }
                    disabled={Boolean(slot.fixed_currency)}
                    allowDeselect={false}
                  />
                </Group>
              ))}

              {selectedOperation.requires_client && (
                <Group grow>
                  <TextInput
                    label="Клиент"
                    value={clientName}
                    onChange={(event) => setClientName(event.currentTarget.value)}
                  />
                  <TextInput
                    label="Документ"
                    value={clientDocument}
                    onChange={(event) => setClientDocument(event.currentTarget.value)}
                  />
                </Group>
              )}

              <TextInput
                label="Комментарий"
                value={comment}
                onChange={(event) => setComment(event.currentTarget.value)}
              />

              <Group justify="flex-end">
                <Button loading={submitting} onClick={() => void handleSubmit()}>
                  Провести
                </Button>
              </Group>
            </>
          )}
        </Stack>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <Stack>
          <Text fw={500}>Последние операции</Text>
          {journal.length === 0 ? (
            <Text size="sm" c="dimmed">
              Операций по кассе пока нет.
            </Text>
          ) : (
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>№</Table.Th>
                  <Table.Th>Операция</Table.Th>
                  <Table.Th>Суммы</Table.Th>
                  <Table.Th>Время</Table.Th>
                  <Table.Th>Статус</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {journal.map((operation) => (
                  <Table.Tr key={operation.id}>
                    <Table.Td>{operation.number}</Table.Td>
                    <Table.Td>{operation.operation_type_name}</Table.Td>
                    <Table.Td>{amountsText(operation)}</Table.Td>
                    <Table.Td>{dayjs(operation.posted_at).format('DD.MM HH:mm')}</Table.Td>
                    <Table.Td>
                      <Badge
                        color={operation.status === 'reversed' ? 'gray' : 'green'}
                        variant="light"
                      >
                        {operation.status_display}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      {operation.status === 'posted' && hasPermission('operations.reverse') && (
                        <Button
                          size="compact-sm"
                          variant="subtle"
                          color="red"
                          loading={submitting}
                          onClick={() => void handleReverse(operation.id)}
                        >
                          Сторно
                        </Button>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Stack>
      </Card>
    </Stack>
  )
}
