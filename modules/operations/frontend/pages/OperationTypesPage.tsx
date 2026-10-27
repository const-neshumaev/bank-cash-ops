import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconAlertCircle,
  IconEdit,
  IconHistory,
  IconPlus,
  IconPrinter,
  IconTrash,
} from '@tabler/icons-react'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import { useAuth } from '@app/auth/AuthContext'

import * as operationTypesApi from '../api/operationTypes'
import type {
  ClientDataPolicy,
  CurrencyOption,
  HistoryValue,
  OperationPrintConfigPayload,
  OperationTypeSettings,
  OperationTypeSettingsChange,
  PrintDocumentTypeOption,
  RateTypeOption,
  ThresholdTypeOption,
} from '../api/operationTypes'

const MANAGE_PERMISSION = 'operations.types.manage'

const POLICY_OPTIONS: ClientDataPolicy[] = ['never', 'always', 'threshold']

interface PrintDocumentSelection {
  documentType: string | null
  template: string | null
  isActive: boolean
}

function formatDateTime(value: string): string {
  return dayjs(value).format('DD.MM.YYYY HH:mm')
}

function kindLabelKey(kind: string): string {
  return `operationTypes.kind.${kind}`
}

export function OperationTypesPage() {
  const { t } = useTranslation('operations')
  const { hasPermission } = useAuth()
  const canManage = hasPermission(MANAGE_PERMISSION)

  const [activeTab, setActiveTab] = useState<string | null>('settings')
  const [types, setTypes] = useState<OperationTypeSettings[]>([])
  const [thresholdTypes, setThresholdTypes] = useState<ThresholdTypeOption[]>([])
  const [currencies, setCurrencies] = useState<CurrencyOption[]>([])
  const [rateTypes, setRateTypes] = useState<RateTypeOption[]>([])
  const [printTypes, setPrintTypes] = useState<PrintDocumentTypeOption[]>([])
  const [loading, setLoading] = useState(false)

  const [editing, setEditing] = useState<OperationTypeSettings | null>(null)
  const [policy, setPolicy] = useState<ClientDataPolicy>('never')
  const [thresholdType, setThresholdType] = useState<string | null>(null)
  const [thresholdValue, setThresholdValue] = useState('')
  const [thresholdCurrency, setThresholdCurrency] = useState<string | null>(null)
  const [rateType, setRateType] = useState<string | null>(null)
  const [isActive, setIsActive] = useState(true)
  const [saving, setSaving] = useState(false)

  const [historyType, setHistoryType] = useState<string | null>(null)
  const [history, setHistory] = useState<OperationTypeSettingsChange[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const [printTarget, setPrintTarget] = useState<OperationTypeSettings | null>(null)
  const [printSelection, setPrintSelection] = useState<PrintDocumentSelection[]>([])
  const [printLoading, setPrintLoading] = useState(false)
  const [printSaving, setPrintSaving] = useState(false)

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
      const [typeRows, thresholdRows, currencyRows, rateTypeRows, printTypeRows] =
        await Promise.all([
          operationTypesApi.listOperationTypeSettings(),
          operationTypesApi.listThresholdTypes(),
          operationTypesApi.listActiveCurrencies(),
          operationTypesApi.listRateTypes(),
          operationTypesApi.listAvailablePrintDocumentTypes(),
        ])
      setTypes(typeRows)
      setThresholdTypes(thresholdRows)
      setCurrencies(currencyRows)
      setRateTypes(rateTypeRows)
      setPrintTypes(printTypeRows)
    } catch (error) {
      notifyError(error)
    } finally {
      setLoading(false)
    }
  }, [notifyError])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!historyType) {
      setHistory([])
      return
    }
    setHistoryLoading(true)
    operationTypesApi
      .fetchOperationTypeHistory(historyType)
      .then(setHistory)
      .catch(notifyError)
      .finally(() => setHistoryLoading(false))
  }, [historyType, notifyError])

  const currencyOptions = useMemo(
    () =>
      currencies.map((currency) => ({
        value: currency.code,
        label: `${currency.code} — ${currency.name}`,
      })),
    [currencies],
  )

  const thresholdOptions = useMemo(
    () => thresholdTypes.map((item) => ({ value: item.code, label: item.name })),
    [thresholdTypes],
  )

  const rateTypeOptions = useMemo(() => {
    if (!editing) return []
    return rateTypes
      .filter((item) => !editing.rate_principle || item.principle === editing.rate_principle)
      .map((item) => ({ value: item.code, label: item.name }))
  }, [editing, rateTypes])

  const selectedThresholdType = thresholdTypes.find((item) => item.code === thresholdType)

  const openEdit = (operationType: OperationTypeSettings) => {
    setEditing(operationType)
    setPolicy(operationType.client_data_policy)
    setThresholdType(operationType.threshold_type || null)
    setThresholdValue(operationType.threshold_value ?? '')
    setThresholdCurrency(operationType.threshold_currency || null)
    setRateType(operationType.rate_type || null)
    setIsActive(operationType.is_active)
  }

  const closeEdit = () => setEditing(null)

  const save = async () => {
    if (!editing) return
    if (editing.kind === 'exchange' && !rateType) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: t('operationTypes.form.rateTypeRequired'),
      })
      return
    }
    setSaving(true)
    try {
      await operationTypesApi.updateOperationTypeSettings(editing.code, {
        client_data_policy: policy,
        threshold_type: policy === 'threshold' ? thresholdType ?? '' : '',
        threshold_value: policy === 'threshold' ? thresholdValue || null : null,
        threshold_currency:
          policy === 'threshold' && selectedThresholdType?.requires_currency
            ? thresholdCurrency ?? ''
            : '',
        rate_type: editing.kind === 'exchange' ? rateType ?? '' : '',
        is_active: isActive,
      })
      notifications.show({ color: 'green', message: t('operationTypes.saved') })
      closeEdit()
      await load()
    } catch (error) {
      notifyError(error)
    } finally {
      setSaving(false)
    }
  }

  const openPrintConfig = async (operationType: OperationTypeSettings) => {
    setPrintTarget(operationType)
    setPrintLoading(true)
    try {
      const configs = await operationTypesApi.fetchOperationPrintConfigs(operationType.code)
      setPrintSelection(
        configs.map((config) => ({
          documentType: config.document_type,
          template: config.template,
          isActive: config.is_active,
        })),
      )
    } catch (error) {
      notifyError(error)
    } finally {
      setPrintLoading(false)
    }
  }

  const closePrintConfig = () => {
    setPrintTarget(null)
    setPrintSelection([])
  }

  const addPrintDocument = () => {
    setPrintSelection((current) => [
      ...current,
      { documentType: null, template: null, isActive: true },
    ])
  }

  const updatePrintDocument = (index: number, patch: Partial<PrintDocumentSelection>) => {
    setPrintSelection((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    )
  }

  const removePrintDocument = (index: number) => {
    setPrintSelection((current) => current.filter((_row, rowIndex) => rowIndex !== index))
  }

  const savePrintConfig = async () => {
    if (!printTarget) return
    const configs: OperationPrintConfigPayload[] = printSelection
      .filter((row) => Boolean(row.documentType && row.template))
      .map((row) => ({
        document_type: row.documentType as string,
        template: row.template as string,
        is_active: row.isActive,
      }))
    setPrintSaving(true)
    try {
      await operationTypesApi.updateOperationPrintConfigs(printTarget.code, configs)
      notifications.show({ color: 'green', message: t('operationTypes.print.saved') })
      closePrintConfig()
      await load()
    } catch (error) {
      notifyError(error)
    } finally {
      setPrintSaving(false)
    }
  }

  const policyLabel = (value: ClientDataPolicy) => t(`operationTypes.policy.${value}`)

  const allTemplateCodes = new Set(
    printTypes.flatMap((documentType) =>
      documentType.templates
        .filter((template) => template.is_active)
        .map((template) => template.code),
    ),
  )
  const selectedTemplateCodes = new Set(
    printSelection
      .map((row) => row.template)
      .filter((code): code is string => Boolean(code)),
  )
  const allTemplatesSelected =
    allTemplateCodes.size === 0 ||
    [...allTemplateCodes].every((code) => selectedTemplateCodes.has(code))

  const thresholdSummary = (operationType: OperationTypeSettings) => {
    if (operationType.client_data_policy !== 'threshold') {
      return '—'
    }
    const typeLabel =
      operationType.threshold_type_display ||
      thresholdTypes.find((item) => item.code === operationType.threshold_type)?.name ||
      operationType.threshold_type
    const value = operationType.threshold_value ?? '—'
    const currency = operationType.threshold_currency
      ? ` ${operationType.threshold_currency}`
      : ''
    return `${value} ${typeLabel}${currency}`.trim()
  }

  const historyValue = (field: string, value: HistoryValue): string => {
    if (value === null || value === '') return '—'
    if (field === 'client_data_policy') return policyLabel(value as ClientDataPolicy)
    if (field === 'threshold_type') {
      return thresholdTypes.find((item) => item.code === value)?.name ?? String(value)
    }
    if (field === 'rate_type') {
      return rateTypes.find((item) => item.code === value)?.name ?? String(value)
    }
    if (field === 'is_active') {
      return value ? t('operationTypes.active') : t('operationTypes.inactive')
    }
    return String(value)
  }

  return (
    <Stack>
      <Title order={3}>{t('operationTypes.title')}</Title>

      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tabs.List>
          <Tabs.Tab value="settings">{t('operationTypes.tabs.settings')}</Tabs.Tab>
          <Tabs.Tab value="history">{t('operationTypes.tabs.history')}</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="settings" pt="md">
          <Table striped highlightOnHover withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('operationTypes.columns.name')}</Table.Th>
                <Table.Th>{t('operationTypes.columns.kind')}</Table.Th>
                <Table.Th>{t('operationTypes.columns.clientData')}</Table.Th>
                <Table.Th>{t('operationTypes.columns.threshold')}</Table.Th>
                <Table.Th>{t('operationTypes.columns.rateType')}</Table.Th>
                <Table.Th>{t('operationTypes.columns.status')}</Table.Th>
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
              ) : types.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={7}>
                    <Center py="md">
                      <Text c="dimmed">{t('operationTypes.empty')}</Text>
                    </Center>
                  </Table.Td>
                </Table.Tr>
              ) : (
                types.map((operationType) => (
                  <Table.Tr key={operationType.code}>
                    <Table.Td>
                      <Text fw={500}>{operationType.name}</Text>
                      <Text size="xs" c="dimmed">
                        {operationType.code}
                      </Text>
                    </Table.Td>
                    <Table.Td>{t(kindLabelKey(operationType.kind))}</Table.Td>
                    <Table.Td>
                      <Badge variant="light">
                        {policyLabel(operationType.client_data_policy)}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{thresholdSummary(operationType)}</Table.Td>
                    <Table.Td>{operationType.rate_type_display || '—'}</Table.Td>
                    <Table.Td>
                      <Badge color={operationType.is_active ? 'teal' : 'gray'} variant="light">
                        {operationType.is_active
                          ? t('operationTypes.active')
                          : t('operationTypes.inactive')}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} justify="flex-end">
                        <Tooltip label={t('operationTypes.print.title')}>
                          <ActionIcon
                            variant="subtle"
                            onClick={() => void openPrintConfig(operationType)}
                          >
                            <IconPrinter size={16} />
                          </ActionIcon>
                        </Tooltip>
                        <Tooltip label={t('operationTypes.historyFor')}>
                          <ActionIcon
                            variant="subtle"
                            onClick={() => {
                              setHistoryType(operationType.code)
                              setActiveTab('history')
                            }}
                          >
                            <IconHistory size={16} />
                          </ActionIcon>
                        </Tooltip>
                        {canManage && (
                          <Tooltip label={t('common.edit')}>
                            <ActionIcon variant="subtle" onClick={() => openEdit(operationType)}>
                              <IconEdit size={16} />
                            </ActionIcon>
                          </Tooltip>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        </Tabs.Panel>

        <Tabs.Panel value="history" pt="md">
          <Stack>
            <Select
              label={t('operationTypes.historyType')}
              placeholder={t('operationTypes.historyTypePlaceholder')}
              data={types.map((item) => ({ value: item.code, label: item.name }))}
              searchable
              value={historyType}
              onChange={setHistoryType}
              w={360}
            />
            <Table striped highlightOnHover withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('operationTypes.columns.changedAt')}</Table.Th>
                  <Table.Th>{t('operationTypes.columns.changedBy')}</Table.Th>
                  <Table.Th>{t('operationTypes.columns.changes')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {historyLoading ? (
                  <Table.Tr>
                    <Table.Td colSpan={3}>
                      <Center py="md">
                        <Loader size="sm" />
                      </Center>
                    </Table.Td>
                  </Table.Tr>
                ) : history.length === 0 ? (
                  <Table.Tr>
                    <Table.Td colSpan={3}>
                      <Center py="md">
                        <Text c="dimmed">{t('operationTypes.historyEmpty')}</Text>
                      </Center>
                    </Table.Td>
                  </Table.Tr>
                ) : (
                  history.map((entry) => (
                    <Table.Tr key={entry.id}>
                      <Table.Td>{formatDateTime(entry.changed_at)}</Table.Td>
                      <Table.Td>{entry.changed_by_email || '—'}</Table.Td>
                      <Table.Td>
                        <Stack gap={2}>
                          {Object.entries(entry.changes).map(([field, change]) => (
                            <Text key={field} size="sm">
                              <Text span fw={500}>
                                {t(`operationTypes.fields.${field}`, { defaultValue: field })}
                              </Text>
                              {': '}
                              {historyValue(field, change.before)}
                              {' → '}
                              {historyValue(field, change.after)}
                            </Text>
                          ))}
                        </Stack>
                      </Table.Td>
                    </Table.Tr>
                  ))
                )}
              </Table.Tbody>
            </Table>
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <Modal
        opened={Boolean(editing)}
        onClose={closeEdit}
        title={editing?.name ?? t('operationTypes.editTitle')}
        size="lg"
      >
        <Stack>
          <Select
            label={t('operationTypes.form.clientDataPolicy')}
            data={POLICY_OPTIONS.map((value) => ({
              value,
              label: policyLabel(value),
            }))}
            value={policy}
            onChange={(value) => setPolicy((value as ClientDataPolicy) ?? 'never')}
            allowDeselect={false}
          />

          {editing?.kind === 'exchange' && (
            <Select
              label={t('operationTypes.form.rateType')}
              data={rateTypeOptions}
              value={rateType}
              onChange={setRateType}
              required
              error={
                !rateType ? t('operationTypes.form.rateTypeRequired') : undefined
              }
              allowDeselect={false}
            />
          )}

          {policy === 'threshold' && (
            <>
              <Select
                label={t('operationTypes.form.thresholdType')}
                data={thresholdOptions}
                value={thresholdType}
                onChange={setThresholdType}
                allowDeselect={false}
              />
              <TextInput
                label={t('operationTypes.form.thresholdValue')}
                placeholder="0.00"
                inputMode="decimal"
                value={thresholdValue}
                onChange={(event) => setThresholdValue(event.currentTarget.value)}
              />
              <Text size="xs" c="dimmed">
                {selectedThresholdType?.requires_currency
                  ? t('operationTypes.form.thresholdValueHintCurrency')
                  : t('operationTypes.form.thresholdValueHintBaseValue')}
              </Text>
              {selectedThresholdType?.requires_currency && (
                <Select
                  label={t('operationTypes.form.thresholdCurrency')}
                  data={currencyOptions}
                  searchable
                  value={thresholdCurrency}
                  onChange={setThresholdCurrency}
                  allowDeselect={false}
                />
              )}
            </>
          )}

          <Switch
            label={t('operationTypes.form.active')}
            checked={isActive}
            onChange={(event) => setIsActive(event.currentTarget.checked)}
          />

          <Group justify="flex-end">
            <Button variant="default" onClick={closeEdit}>
              {t('common.cancel')}
            </Button>
            <Button
              loading={saving}
              disabled={editing?.kind === 'exchange' && !rateType}
              onClick={() => void save()}
            >
              {t('common.save')}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={Boolean(printTarget)}
        onClose={closePrintConfig}
        title={t('operationTypes.print.modalTitle', { name: printTarget?.name ?? '' })}
        size="lg"
      >
        {printLoading ? (
          <Center py="md">
            <Loader size="sm" />
          </Center>
        ) : (
          <Stack>
            <Text size="sm" c="dimmed">
              {t('operationTypes.print.hint')}
            </Text>
            {printTypes.length === 0 && (
              <Alert color="blue" icon={<IconAlertCircle size={16} />}>
                {t('operationTypes.print.empty')}
              </Alert>
            )}
            {printSelection.length === 0 && (
              <Text size="xs" c="dimmed">
                {t('operationTypes.print.noDocuments')}
              </Text>
            )}
            {printSelection.map((row, index) => {
              const documentType = printTypes.find((item) => item.code === row.documentType)
              const templates = (documentType?.templates ?? []).filter(
                (template) => template.is_active,
              )
              const selectedTemplate = templates.find((template) => template.code === row.template)
              const usedByOtherRows = new Set(
                printSelection
                  .filter((_item, rowIndex) => rowIndex !== index)
                  .map((item) => item.template)
                  .filter((code): code is string => Boolean(code)),
              )
              const availableTemplates = templates.filter(
                (template) =>
                  template.code === row.template || !usedByOtherRows.has(template.code),
              )
              return (
                <Stack key={index} gap={4}>
                  <Group align="flex-end" wrap="nowrap">
                    <Select
                      style={{ flex: 1 }}
                      label={t('operationTypes.print.documentType')}
                      placeholder={t('operationTypes.print.documentTypePlaceholder')}
                      data={printTypes.map((item) => ({
                        value: item.code,
                        label: item.name,
                      }))}
                      value={row.documentType}
                      onChange={(value) =>
                        updatePrintDocument(index, { documentType: value, template: null })
                      }
                      clearable
                    />
                    <Select
                      style={{ flex: 1 }}
                      label={t('operationTypes.print.template')}
                      placeholder={t('operationTypes.print.noTemplate')}
                      data={availableTemplates.map((template) => ({
                        value: template.code,
                        label: template.name,
                      }))}
                      value={row.template}
                      onChange={(value) => updatePrintDocument(index, { template: value })}
                      disabled={!row.documentType || availableTemplates.length === 0}
                      clearable
                    />
                    <ActionIcon
                      color="red"
                      variant="subtle"
                      aria-label={t('operationTypes.print.remove')}
                      onClick={() => removePrintDocument(index)}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                  {selectedTemplate && (
                    <Switch
                      label={t('operationTypes.print.active')}
                      checked={row.isActive}
                      onChange={(event) =>
                        updatePrintDocument(index, { isActive: event.currentTarget.checked })
                      }
                    />
                  )}
                  {selectedTemplate && !selectedTemplate.has_file && (
                    <Text size="xs" c="red">
                      {t('operationTypes.print.noFile')}
                    </Text>
                  )}
                </Stack>
              )
            })}
            <Button
              variant="light"
              size="xs"
              leftSection={<IconPlus size={14} />}
              disabled={allTemplatesSelected}
              onClick={addPrintDocument}
            >
              {t('operationTypes.print.addDocument')}
            </Button>
            <Group justify="flex-end">
              <Button variant="default" onClick={closePrintConfig}>
                {t('common.cancel')}
              </Button>
              <Button
                loading={printSaving}
                disabled={!canManage}
                onClick={() => void savePrintConfig()}
              >
                {t('common.save')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  )
}
