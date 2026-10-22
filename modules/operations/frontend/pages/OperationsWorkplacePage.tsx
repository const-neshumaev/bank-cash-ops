import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  Loader,
  Modal,
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
import { useTranslation } from 'react-i18next'
import { NavLink as RouterNavLink } from 'react-router-dom'

import { extractErrorMessage } from '@app/api/errors'
import { useAuth } from '@app/auth/AuthContext'

import * as operationsApi from '../api/operations'
import type {
  ClientDataRequirement,
  Currency,
  Operation,
  OperationLine,
  PreviewOperation,
  WorkplaceContext,
  WorkplaceOperation,
} from '../api/operations'
import {
  computeAmount,
  currencyOptions,
  exchangeSlots,
  formatAmount,
  formatRate,
  parseAmount,
  resolveRate,
} from '../operationForm'

function currencyLabel(code: string, currencies: Currency[]): string {
  const currency = currencies.find((item) => item.code === code)
  return currency ? `${currency.code} — ${currency.name}` : code
}

/** i18n keys of the rate-type labels (under `workplace.rateType.*`). */
const RATE_TYPE_LABEL_KEYS: Record<string, string> = {
  buy: 'workplace.rateType.buy',
  sell: 'workplace.rateType.sell',
  central: 'workplace.rateType.central',
}

function amountsText(operation: Operation): string {
  return operation.lines.map((line) => `${line.amount} ${line.currency}`).join(', ')
}

function slotName(operation: WorkplaceOperation | undefined, code: string): string {
  return operation?.slots.find((slot) => slot.code === code)?.name ?? code
}

function allowsCurrency(
  slotPolicy: string,
  baseCurrency: string,
  currency: string,
): boolean {
  if (slotPolicy === 'base') return currency === baseCurrency
  if (slotPolicy === 'foreign') return currency !== baseCurrency
  return true
}

export function OperationsWorkplacePage() {
  const { t } = useTranslation('operations')
  const { hasPermission } = useAuth()
  const canCreate = hasPermission('operations.create')
  const [context, setContext] = useState<WorkplaceContext | null>(null)
  const [journal, setJournal] = useState<Operation[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const [operationModalOpen, setOperationModalOpen] = useState(false)
  const [operationCode, setOperationCode] = useState<string | null>(null)

  const [slotAmounts, setSlotAmounts] = useState<Record<string, string>>({})
  const [slotCurrencies, setSlotCurrencies] = useState<Record<string, string>>({})
  const [multiAmounts, setMultiAmounts] = useState<Record<string, string>>({})

  const [exchangeAmount, setExchangeAmount] = useState('')
  const [basisCurrency, setBasisCurrency] = useState<string | null>(null)
  const [computedCurrency, setComputedCurrency] = useState<string | null>(null)
  const [individualRate, setIndividualRate] = useState(false)
  const [rateInput, setRateInput] = useState('')

  const [clientName, setClientName] = useState('')
  const [clientDocument, setClientDocument] = useState('')
  const [comment, setComment] = useState('')
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const [clientRequirement, setClientRequirement] = useState<ClientDataRequirement | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [pendingPreview, setPendingPreview] = useState<PreviewOperation | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const [reverseTarget, setReverseTarget] = useState<Operation | null>(null)

  const selectedOperation = useMemo<WorkplaceOperation | undefined>(
    () => context?.operations.find((item) => item.code === operationCode),
    [context, operationCode],
  )
  const exchange = useMemo(
    () => (selectedOperation ? exchangeSlots(selectedOperation) : null),
    [selectedOperation],
  )

  const resolvedRate = useMemo(() => {
    if (!context || !selectedOperation || !exchange || !basisCurrency || !computedCurrency) {
      return null
    }
    return resolveRate(context, selectedOperation, basisCurrency, computedCurrency)
  }, [context, selectedOperation, exchange, basisCurrency, computedCurrency])

  const effectiveRate = individualRate ? parseAmount(rateInput) : resolvedRate

  const computedAmount = useMemo(() => {
    if (!exchange || !effectiveRate) return 0
    return computeAmount(parseAmount(exchangeAmount), effectiveRate, exchange.computed.computation)
  }, [exchange, effectiveRate, exchangeAmount])

  const rateTypeLabel = (rateType: string) => t(RATE_TYPE_LABEL_KEYS[rateType] ?? rateType)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await operationsApi.fetchWorkplace()
      setContext(data)
      setJournal(data.cash_desk_id === null ? [] : await operationsApi.listOperations(data.cash_desk_id))
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  const resetOperationForm = useCallback(() => {
    setOperationCode(null)
    setSlotAmounts({})
    setSlotCurrencies({})
    setMultiAmounts({})
    setExchangeAmount('')
    setBasisCurrency(null)
    setComputedCurrency(null)
    setIndividualRate(false)
    setRateInput('')
    setClientName('')
    setClientDocument('')
    setComment('')
    setSubmitAttempted(false)
    setClientRequirement(null)
    setPreviewError(null)
    setPendingPreview(null)
  }, [])

  const openOperationModal = () => {
    resetOperationForm()
    setOperationModalOpen(true)
  }

  const closeOperationModal = () => {
    setOperationModalOpen(false)
    resetOperationForm()
  }

  const selectOperation = (code: string | null) => {
    setOperationCode(code)
    setSlotAmounts({})
    setSlotCurrencies({})
    setMultiAmounts({})
    setExchangeAmount('')
    setIndividualRate(false)
    setRateInput('')
    setClientName('')
    setClientDocument('')
    setComment('')
    setSubmitAttempted(false)
    setClientRequirement(null)
    setPreviewError(null)
    setPendingPreview(null)

    if (!context || !code) {
      setBasisCurrency(null)
      setComputedCurrency(null)
      return
    }

    const operation = context.operations.find((item) => item.code === code)
    if (!operation) return

    if (operation.form === 'multi_currency') {
      const prefilled: Record<string, string> = {}
      for (const currency of context.currencies) {
        const balance = context.balances.find((row) => row.currency === currency.code)
        prefilled[currency.code] =
          operation.kind === 'expense' && balance ? balance.amount : ''
      }
      setMultiAmounts(prefilled)
      return
    }

    if (operation.form === 'amount') {
      const currencies: Record<string, string> = {}
      for (const slot of operation.slots) {
        const defaultCurrency =
          slot.currency_policy === 'base'
            ? context.base_currency
            : slot.currency_policy === 'foreign'
              ? context.currencies.find(
                  (currency) => currency.code !== context.base_currency,
                )?.code ?? ''
              : context.currencies[0]?.code ?? ''
        currencies[slot.code] = slot.fixed_currency || defaultCurrency
      }
      setSlotCurrencies(currencies)
      return
    }

    const slots = exchangeSlots(operation)
    if (!slots) return

    const base = context.base_currency
    const foreign = context.currencies.filter((currency) => currency.code !== base)
    const initialBasis =
      slots.basis.currency_policy === 'base'
        ? base
        : slots.basis.fixed_currency || foreign[0]?.code || base
    const initialComputed =
      slots.computed.currency_policy === 'base'
        ? base
        : slots.computed.fixed_currency ||
          foreign.find((currency) => currency.code !== initialBasis)?.code ||
          base
    setBasisCurrency(initialBasis)
    setComputedCurrency(initialComputed)
  }

  const buildDraftLines = useCallback((): OperationLine[] | null => {
    if (!context || !selectedOperation) return null

    if (selectedOperation.form === 'exchange' && exchange) {
      if (!basisCurrency || !computedCurrency || !effectiveRate) return null
      const basisAmount = parseAmount(exchangeAmount)
      if (basisAmount <= 0) return null
      const rateValue = String(effectiveRate)
      const basisLine: OperationLine = {
        slot: exchange.basis.code,
        currency: basisCurrency,
        amount: formatAmount(basisAmount, basisCurrency, context.currencies),
        rate: exchange.rate.code === exchange.basis.code ? rateValue : null,
        rate_is_individual: exchange.rate.code === exchange.basis.code ? individualRate : false,
      }
      const computedLine: OperationLine = {
        slot: exchange.computed.code,
        currency: computedCurrency,
        amount: formatAmount(computedAmount, computedCurrency, context.currencies),
        rate: exchange.rate.code === exchange.computed.code ? rateValue : null,
        rate_is_individual:
          exchange.rate.code === exchange.computed.code ? individualRate : false,
      }
      return [basisLine, computedLine]
    }

    if (selectedOperation.form === 'multi_currency') {
      const slot = selectedOperation.slots.find((item) => item.multiple) ?? selectedOperation.slots[0]
      if (!slot) return null
      return context.currencies
        .filter((currency) => parseAmount(multiAmounts[currency.code] ?? '') > 0)
        .map((currency) => ({
          slot: slot.code,
          currency: currency.code,
          amount: multiAmounts[currency.code],
          rate: null,
          rate_is_individual: false,
        }))
    }

    const lines: OperationLine[] = []
    for (const slot of selectedOperation.slots) {
      const currency =
        slot.fixed_currency || slotCurrencies[slot.code] || context.base_currency
      lines.push({
        slot: slot.code,
        currency,
        amount: slotAmounts[slot.code] ?? '',
        rate: null,
        rate_is_individual: false,
      })
    }
    if (lines.some((line) => parseAmount(line.amount) <= 0)) return null
    return lines
  }, [
    context,
    selectedOperation,
    exchange,
    basisCurrency,
    computedCurrency,
    effectiveRate,
    exchangeAmount,
    computedAmount,
    multiAmounts,
    slotAmounts,
    slotCurrencies,
    individualRate,
  ])

  const draftLines = useMemo(() => buildDraftLines(), [buildDraftLines])

  useEffect(() => {
    if (!operationModalOpen || !selectedOperation) {
      setClientRequirement(null)
      return
    }
    if (selectedOperation.client_data_policy === 'always') {
      setClientRequirement({
        policy: 'always',
        required: true,
        reason: 'always',
        amount: null,
        threshold: null,
        currency: '',
      })
      setPreviewError(null)
      return
    }
    if (selectedOperation.client_data_policy !== 'threshold') {
      setClientRequirement(null)
      return
    }
    if (!draftLines || draftLines.length === 0) {
      setClientRequirement(null)
      return
    }

    let cancelled = false
    const timer = setTimeout(() => {
      operationsApi
        .previewOperation({
          operation_type: selectedOperation.code,
          lines: draftLines,
        })
        .then((preview) => {
          if (!cancelled) {
            setClientRequirement(preview.client_data)
            setPreviewError(null)
          }
        })
        .catch((error) => {
          if (!cancelled) {
            setClientRequirement(null)
            setPreviewError(extractErrorMessage(error))
          }
        })
    }, 400)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [operationModalOpen, selectedOperation, draftLines])

  const clientDataRequired = Boolean(clientRequirement?.required)

  const clientDataErrorMessage = (requirement: ClientDataRequirement): string => {
    if (requirement.reason === 'always') {
      return t('workplace.clientData.reasonAlways')
    }
    const amount = requirement.amount
      ? formatAmount(
          Number(requirement.amount),
          requirement.currency,
          context?.currencies ?? [],
        )
      : requirement.amount ?? ''
    const threshold = requirement.threshold
      ? formatAmount(
          Number(requirement.threshold),
          requirement.currency,
          context?.currencies ?? [],
        )
      : requirement.threshold ?? ''
    return t('workplace.clientData.reasonThreshold', {
      amount,
      threshold,
      currency: requirement.currency,
    })
  }

  const handleSubmit = async () => {
    if (!selectedOperation) return
    setSubmitAttempted(true)
    if (!draftLines || draftLines.length === 0) {
      notifications.show({ color: 'red', title: t('common.error'), message: t('validation.amounts') })
      return
    }
    setSubmitting(true)
    setPreviewError(null)
    try {
      const preview = await operationsApi.previewOperation({
        operation_type: selectedOperation.code,
        lines: draftLines,
        client_name: clientName,
        client_document: clientDocument,
        comment,
      })
      setClientRequirement(preview.client_data)
      if (preview.client_data.required && (!clientName.trim() || !clientDocument.trim())) {
        notifications.show({
          color: 'red',
          title: t('common.error'),
          message: t('validation.clientData'),
        })
        return
      }
      setPendingPreview(preview)
      setConfirmOpen(true)
    } catch (error) {
      setPreviewError(extractErrorMessage(error))
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleConfirm = async () => {
    if (!pendingPreview) return
    setSubmitting(true)
    try {
      await operationsApi.postOperation({
        operation_type: pendingPreview.operation_type,
        lines: pendingPreview.lines.map((line) => ({
          slot: line.slot,
          currency: line.currency,
          amount: line.amount,
          rate: line.rate,
          rate_is_individual: line.rate_is_individual ?? false,
        })),
        client_name: clientName,
        client_document: clientDocument,
        comment,
        idempotency_key: crypto.randomUUID(),
      })
      notifications.show({ color: 'green', message: t('workplace.posted') })
      setConfirmOpen(false)
      closeOperationModal()
      await load()
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleReverse = async () => {
    if (!reverseTarget) return
    setSubmitting(true)
    try {
      await operationsApi.reverseOperation(reverseTarget.id)
      notifications.show({ color: 'green', message: t('workplace.reversed') })
      setReverseTarget(null)
      await load()
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
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
        <Title order={3}>{t('workplace.title')}</Title>
        <Alert
          color="yellow"
          icon={<IconAlertCircle size={16} />}
          title={t('workplace.noShift.title')}
        >
          <Stack gap="sm" align="flex-start">
            <Text size="sm">{t('workplace.noShift.message')}</Text>
            <Button component={RouterNavLink} to="/workplace" variant="light">
              {t('workplace.noShift.open')}
            </Button>
          </Stack>
        </Alert>
      </Stack>
    )
  }

  const baseCurrency = context.base_currency
  const inputCurrencyOptions = (slotPolicy: string, excluded: string[] = []) =>
    currencyOptions(
      context.currencies.filter((currency) =>
        allowsCurrency(slotPolicy, baseCurrency, currency.code),
      ),
      excluded,
    )

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>{t('workplace.title')}</Title>
        <Badge variant="light">{t('workplace.shiftBadge', { id: context.shift_id })}</Badge>
      </Group>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Text fw={500}>{t('workplace.balances.title')}</Text>
          {context.balances.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t('workplace.balances.empty')}
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
            <Text fw={500}>{t('workplace.rates.title')}</Text>
            <Group gap="xl">
              {context.rates.map((rate) => (
                <Text key={`${rate.currency}-${rate.base_currency}-${rate.rate_type}`} size="sm">
                  {rate.units} {rate.currency} = <b>{rate.value}</b> {rate.base_currency} (
                  {rateTypeLabel(rate.rate_type)})
                </Text>
              ))}
            </Group>
          </Stack>
        </Card>
      )}

      <Card withBorder padding="lg" radius="md">
        <Group justify="space-between">
          <Stack gap={2}>
            <Text fw={500}>{t('workplace.newOperation')}</Text>
            <Text size="sm" c="dimmed">
              {t('workplace.newOperationHint')}
            </Text>
          </Stack>
          <Button onClick={openOperationModal} disabled={!canCreate}>
            {t('workplace.createOperation')}
          </Button>
        </Group>
      </Card>

      <Modal
        opened={operationModalOpen}
        onClose={closeOperationModal}
        title={t('workplace.newOperation')}
        size="xl"
      >
        <Stack>
          <Select
            label={t('workplace.operation')}
            placeholder={t('workplace.operationPlaceholder')}
            data={context.operations.map((item) => ({ value: item.code, label: item.name }))}
            value={operationCode}
            onChange={selectOperation}
            searchable
            nothingFoundMessage={t('workplace.operationNotFound')}
          />

          {selectedOperation && (
            <>
              {selectedOperation.form === 'multi_currency' &&
                selectedOperation.slots.length > 0 &&
                context.currencies.map((currency) => (
                  <TextInput
                    key={currency.code}
                    label={currencyLabel(currency.code, context.currencies)}
                    placeholder="0.00"
                    inputMode="decimal"
                    value={multiAmounts[currency.code] ?? ''}
                    onChange={(event) =>
                      setMultiAmounts((prev) => ({
                        ...prev,
                        [currency.code]: event.currentTarget.value,
                      }))
                    }
                  />
                ))}

              {selectedOperation.form === 'amount' &&
                selectedOperation.slots.map((slot) => (
                  <Group key={slot.code} align="flex-end" grow>
                    <TextInput
                      label={slot.name}
                      placeholder="0.00"
                      inputMode="decimal"
                      value={slotAmounts[slot.code] ?? ''}
                      onChange={(event) =>
                        setSlotAmounts((prev) => ({
                          ...prev,
                          [slot.code]: event.currentTarget.value,
                        }))
                      }
                    />
                    <Select
                      label={t('workplace.currency')}
                      data={inputCurrencyOptions(slot.currency_policy)}
                      value={
                        slot.fixed_currency ||
                        slotCurrencies[slot.code] ||
                        (slot.currency_policy === 'base' ? baseCurrency : null)
                      }
                      onChange={(value) =>
                        setSlotCurrencies((prev) => ({
                          ...prev,
                          [slot.code]: value ?? '',
                        }))
                      }
                      disabled={Boolean(slot.fixed_currency) || slot.currency_policy === 'base'}
                      allowDeselect={false}
                    />
                  </Group>
                ))}

              {selectedOperation.form === 'exchange' && exchange && (
                <Stack>
                  <Group align="flex-end" grow>
                    <TextInput
                      label={exchange.basis.name}
                      placeholder="0.00"
                      inputMode="decimal"
                      value={exchangeAmount}
                      onChange={(event) => setExchangeAmount(event.currentTarget.value)}
                    />
                    <Select
                      label={t('workplace.currency')}
                      data={inputCurrencyOptions(exchange.basis.currency_policy)}
                      value={basisCurrency}
                      onChange={(value) => {
                        setBasisCurrency(value ?? '')
                        if (value && value === computedCurrency) {
                          const alternative = context.currencies.find(
                            (currency) =>
                              currency.code !== value &&
                              currency.code !== baseCurrency,
                          )
                          setComputedCurrency(alternative?.code ?? '')
                        }
                      }}
                      disabled={
                        Boolean(exchange.basis.fixed_currency) ||
                        exchange.basis.currency_policy === 'base'
                      }
                      allowDeselect={false}
                    />
                  </Group>

                  <Group align="flex-end" grow>
                    <TextInput
                      label={exchange.computed.name}
                      value={formatAmount(
                        computedAmount,
                        computedCurrency ?? baseCurrency,
                        context.currencies,
                      )}
                      readOnly
                      disabled
                    />
                    <Select
                      label={t('workplace.currency')}
                      data={inputCurrencyOptions(
                        exchange.computed.currency_policy,
                        basisCurrency ? [basisCurrency] : [],
                      )}
                      value={computedCurrency}
                      onChange={(value) => setComputedCurrency(value ?? '')}
                      disabled={
                        Boolean(exchange.computed.fixed_currency) ||
                        exchange.computed.currency_policy === 'base'
                      }
                      allowDeselect={false}
                    />
                  </Group>

                  <Group align="flex-end" grow>
                    <TextInput
                      label={t('workplace.exchange.rate')}
                      placeholder="0.00000000"
                      inputMode="decimal"
                      value={
                        individualRate
                          ? rateInput
                          : resolvedRate !== null
                            ? formatRate(resolvedRate)
                            : ''
                      }
                      onChange={(event) => setRateInput(event.currentTarget.value)}
                      disabled={!individualRate}
                    />
                    <Checkbox
                      label={t('workplace.exchange.individualRate')}
                      checked={individualRate}
                      tabIndex={-1}
                      onChange={(event) => {
                        const checked = event.currentTarget.checked
                        if (checked && !rateInput && resolvedRate !== null) {
                          setRateInput(formatRate(resolvedRate))
                        }
                        setIndividualRate(checked)
                      }}
                    />
                  </Group>

                  {selectedOperation.rate_type_display && (
                    <Text size="xs" c="dimmed">
                      {t('workplace.exchange.rateType', {
                        name: selectedOperation.rate_type_display,
                      })}
                    </Text>
                  )}
                  {!selectedOperation.rate_type && (
                    <Alert color="red" icon={<IconAlertCircle size={16} />}>
                      {t('workplace.exchange.rateTypeMissing')}
                    </Alert>
                  )}
                  {selectedOperation.rate_type && !resolvedRate && !individualRate && (
                    <Alert color="yellow" icon={<IconAlertCircle size={16} />}>
                      {t('workplace.exchange.rateMissing')}
                    </Alert>
                  )}
                </Stack>
              )}

              {clientDataRequired && clientRequirement && (
                <Card withBorder padding="md" radius="md">
                  <Stack gap="xs">
                    <Text fw={500}>{t('workplace.clientData.title')}</Text>
                    <Alert color="blue" icon={<IconAlertCircle size={16} />}>
                      <Stack gap={2}>
                        <Text size="sm">{t('workplace.clientData.message')}</Text>
                        <Text size="xs" c="dimmed">
                          {clientDataErrorMessage(clientRequirement)}
                        </Text>
                      </Stack>
                    </Alert>
                    <Group grow align="flex-start">
                      <TextInput
                        label={t('workplace.client')}
                        required
                        value={clientName}
                        error={
                          submitAttempted && !clientName.trim()
                            ? t('validation.clientRequired')
                            : undefined
                        }
                        onChange={(event) => setClientName(event.currentTarget.value)}
                      />
                      <TextInput
                        label={t('workplace.document')}
                        required
                        value={clientDocument}
                        error={
                          submitAttempted && !clientDocument.trim()
                            ? t('validation.documentRequired')
                            : undefined
                        }
                        onChange={(event) => setClientDocument(event.currentTarget.value)}
                      />
                    </Group>
                  </Stack>
                </Card>
              )}

              {previewError && (
                <Alert color="red" icon={<IconAlertCircle size={16} />}>
                  {previewError}
                </Alert>
              )}

              <TextInput
                label={t('workplace.comment')}
                value={comment}
                onChange={(event) => setComment(event.currentTarget.value)}
              />

              <Group justify="flex-end">
                <Button variant="default" onClick={closeOperationModal}>
                  {t('common.cancel')}
                </Button>
                <Button loading={submitting} onClick={() => void handleSubmit()}>
                  {t('workplace.post')}
                </Button>
              </Group>
            </>
          )}
        </Stack>
      </Modal>

      <Modal
        opened={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title={t('workplace.confirm.title')}
        size="lg"
      >
        {pendingPreview && selectedOperation && (
          <Stack>
            <Text>{t('workplace.confirm.question', { name: selectedOperation.name })}</Text>
            <Table striped withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('workplace.confirm.slot')}</Table.Th>
                  <Table.Th>{t('workplace.confirm.amount')}</Table.Th>
                  <Table.Th>{t('workplace.confirm.currency')}</Table.Th>
                  <Table.Th>{t('workplace.confirm.rate')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {pendingPreview.lines.map((line) => (
                  <Table.Tr key={`${line.slot}-${line.currency}`}>
                    <Table.Td>{slotName(selectedOperation, line.slot)}</Table.Td>
                    <Table.Td>{line.amount}</Table.Td>
                    <Table.Td>{line.currency}</Table.Td>
                    <Table.Td>{line.rate ?? '—'}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {pendingPreview.client_data.required && (
              <Stack gap={2}>
                <Text size="sm">
                  <b>{t('workplace.client')}:</b> {clientName}
                </Text>
                <Text size="sm">
                  <b>{t('workplace.document')}:</b> {clientDocument}
                </Text>
              </Stack>
            )}
            {comment && (
              <Text size="sm">
                <b>{t('workplace.comment')}:</b> {comment}
              </Text>
            )}
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setConfirmOpen(false)}>
                {t('common.cancel')}
              </Button>
              <Button loading={submitting} onClick={() => void handleConfirm()}>
                {t('workplace.confirm.confirm')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      <Modal
        opened={Boolean(reverseTarget)}
        onClose={() => setReverseTarget(null)}
        title={t('workplace.confirm.reverseTitle')}
        size="md"
      >
        {reverseTarget && (
          <Stack>
            <Text>
              {t('workplace.confirm.reverseQuestion', {
                number: reverseTarget.number,
                name: reverseTarget.operation_type_name,
              })}
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setReverseTarget(null)}>
                {t('common.cancel')}
              </Button>
              <Button color="red" loading={submitting} onClick={() => void handleReverse()}>
                {t('workplace.confirm.reverseConfirm')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      <Card withBorder padding="lg" radius="md">
        <Stack>
          <Text fw={500}>{t('workplace.recent.title')}</Text>
          {journal.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t('workplace.recent.empty')}
            </Text>
          ) : (
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('workplace.recent.number')}</Table.Th>
                  <Table.Th>{t('workplace.recent.operation')}</Table.Th>
                  <Table.Th>{t('workplace.recent.amounts')}</Table.Th>
                  <Table.Th>{t('workplace.recent.time')}</Table.Th>
                  <Table.Th>{t('workplace.recent.status')}</Table.Th>
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
                          onClick={() => setReverseTarget(operation)}
                        >
                          {t('workplace.reverse')}
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
