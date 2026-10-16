import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  Loader,
  Select,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconAlertTriangle,
  IconDeviceFloppy,
  IconKeyboard,
  IconReload,
  IconTemplate,
  IconTrash,
} from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import type { Branch, CashDesk } from '@app/api/types'
import { useAuth } from '@app/auth/AuthContext'

import { listBranches, listCashDesks } from '../api/directories'
import * as configApi from '../api/operationConfig'
import type {
  CashDeskOperations,
  ConfigSource,
  OperationOption,
  OperationTemplate,
} from '../api/operationConfig'

const BANK_PERMISSION = 'operations.config.manage'

/** i18n keys of the operation-kind labels (under `config.kind.*`). */
const KIND_LABEL_KEYS: Record<string, string> = {
  income: 'config.kind.income',
  expense: 'config.kind.expense',
  exchange: 'config.kind.exchange',
  internal: 'config.kind.internal',
}

function sourceColor(source: ConfigSource): string {
  switch (source) {
    case 'own':
      return 'blue'
    case 'branch':
      return 'grape'
    case 'bank':
      return 'teal'
    default:
      return 'red'
  }
}

interface OperationsChecklistProps {
  operations: OperationOption[]
  value: string[]
  onChange: (value: string[]) => void
  disabled?: boolean
}

function OperationsChecklist({
  operations,
  value,
  onChange,
  disabled,
}: OperationsChecklistProps) {
  const { t } = useTranslation('operations')
  return (
    <Checkbox.Group value={value} onChange={onChange}>
      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} mt="xs">
        {operations.map((operation) => (
          <Checkbox
            key={operation.code}
            value={operation.code}
            label={`${operation.name} (${t(KIND_LABEL_KEYS[operation.kind] ?? operation.kind)})`}
            disabled={disabled}
          />
        ))}
      </SimpleGrid>
    </Checkbox.Group>
  )
}

function OperationBadges({ operations }: { operations: OperationOption[] }) {
  const { t } = useTranslation('operations')
  if (operations.length === 0) {
    return (
      <Text c="dimmed" size="sm">
        {t('config.disabled')}
      </Text>
    )
  }
  return (
    <Group gap={6}>
      {operations.map((operation) => (
        <Badge key={operation.code} variant="light">
          {operation.name}
        </Badge>
      ))}
    </Group>
  )
}

export function OperationsConfigPage() {
  const { t } = useTranslation('operations')
  const { hasPermission } = useAuth()
  const canManageBank = hasPermission(BANK_PERMISSION)

  const [operations, setOperations] = useState<OperationOption[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [cashDesks, setCashDesks] = useState<CashDesk[]>([])
  const [templates, setTemplates] = useState<configApi.OperationTemplateSummary[]>([])

  const [deskId, setDeskId] = useState<string | null>(null)
  const [deskConfig, setDeskConfig] = useState<CashDeskOperations | null>(null)
  const [deskEditing, setDeskEditing] = useState(false)
  const [deskDraft, setDeskDraft] = useState<string[]>([])
  const [deskSaving, setDeskSaving] = useState(false)

  const [bankTemplate, setBankTemplate] = useState<OperationTemplate | null>(null)
  const [bankDraft, setBankDraft] = useState<string[]>([])
  const [bankSaving, setBankSaving] = useState(false)

  const [branchId, setBranchId] = useState<string | null>(null)
  const [branchTemplate, setBranchTemplate] = useState<OperationTemplate | null>(null)
  const [branchDraft, setBranchDraft] = useState<string[]>([])
  const [branchSaving, setBranchSaving] = useState(false)

  const branchName = useCallback(
    (id: number) => branches.find((branch) => branch.id === id)?.name ?? `#${id}`,
    [branches],
  )

  const sourceLabel = (source: ConfigSource, templateBranchId: number | null) => {
    switch (source) {
      case 'own':
        return t('config.source.own')
      case 'branch':
        return t('config.source.branch', {
          branch: templateBranchId ? branchName(templateBranchId) : '',
        })
      case 'bank':
        return t('config.source.bank')
      default:
        return t('config.source.none')
    }
  }

  const branchesWithTemplate = useMemo(
    () =>
      new Set(
        templates.map((template) => template.branch_id).filter((id): id is number => id !== null),
      ),
    [templates],
  )

  const notifyError = (error: unknown) =>
    notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })

  const reloadTemplates = useCallback(async () => {
    try {
      setTemplates(await configApi.listOperationTemplates())
    } catch (error) {
      notifyError(error)
    }
  }, [])

  const reloadBankTemplate = useCallback(async () => {
    try {
      const template = await configApi.fetchBankOperationTemplate()
      setBankTemplate(template)
      setBankDraft(template.operations.map((operation) => operation.code))
    } catch (error) {
      notifyError(error)
    }
  }, [])

  useEffect(() => {
    void Promise.all([configApi.listOperationTypes(), listBranches(), listCashDesks()])
      .then(([operationList, branchList, deskList]) => {
        setOperations(operationList)
        setBranches(branchList)
        setCashDesks(deskList)
      })
      .catch(notifyError)
    void reloadTemplates()
    void reloadBankTemplate()
  }, [])

  useEffect(() => {
    if (!deskId) {
      setDeskConfig(null)
      return
    }
    setDeskEditing(false)
    void configApi
      .fetchCashDeskOperations(Number(deskId))
      .then((config) => {
        setDeskConfig(config)
        setDeskDraft(config.operations.map((operation) => operation.code))
      })
      .catch(notifyError)
  }, [deskId])

  useEffect(() => {
    if (!branchId) {
      setBranchTemplate(null)
      return
    }
    void configApi
      .fetchBranchOperationTemplate(Number(branchId))
      .then((template) => {
        setBranchTemplate(template)
        setBranchDraft(template.operations.map((operation) => operation.code))
      })
      .catch(notifyError)
  }, [branchId])

  const saveDesk = async () => {
    if (!deskId) return
    setDeskSaving(true)
    try {
      const config = await configApi.setCashDeskOperations(Number(deskId), deskDraft)
      setDeskConfig(config)
      setDeskEditing(false)
      notifications.show({ color: 'green', message: t('config.saved.desk') })
    } catch (error) {
      notifyError(error)
    } finally {
      setDeskSaving(false)
    }
  }

  const resetDesk = async () => {
    if (!deskId) return
    setDeskSaving(true)
    try {
      const config = await configApi.setCashDeskOperations(Number(deskId), [])
      setDeskConfig(config)
      setDeskDraft(config.operations.map((operation) => operation.code))
      setDeskEditing(false)
      notifications.show({ color: 'green', message: t('config.saved.deskReset') })
    } catch (error) {
      notifyError(error)
    } finally {
      setDeskSaving(false)
    }
  }

  const saveBank = async () => {
    setBankSaving(true)
    try {
      const template = await configApi.setBankOperationTemplate(bankDraft)
      setBankTemplate(template)
      await reloadTemplates()
      notifications.show({ color: 'green', message: t('config.saved.bank') })
    } catch (error) {
      notifyError(error)
    } finally {
      setBankSaving(false)
    }
  }

  const deleteBank = async () => {
    setBankSaving(true)
    try {
      await configApi.deleteBankOperationTemplate()
      await reloadBankTemplate()
      await reloadTemplates()
      notifications.show({ color: 'green', message: t('config.saved.bankDeleted') })
    } catch (error) {
      notifyError(error)
    } finally {
      setBankSaving(false)
    }
  }

  const saveBranch = async () => {
    if (!branchId) return
    setBranchSaving(true)
    try {
      const template = await configApi.setBranchOperationTemplate(Number(branchId), branchDraft)
      setBranchTemplate(template)
      await reloadTemplates()
      notifications.show({ color: 'green', message: t('config.saved.branch') })
    } catch (error) {
      notifyError(error)
    } finally {
      setBranchSaving(false)
    }
  }

  const deleteBranch = async () => {
    if (!branchId) return
    setBranchSaving(true)
    try {
      await configApi.deleteBranchOperationTemplate(Number(branchId))
      await reloadTemplates()
      setBranchTemplate({ branch_id: Number(branchId), defined: false, operations: [] })
      setBranchDraft([])
      notifications.show({ color: 'green', message: t('config.saved.branchDeleted') })
    } catch (error) {
      notifyError(error)
    } finally {
      setBranchSaving(false)
    }
  }

  return (
    <Stack>
      <Title order={3}>{t('config.title')}</Title>

      <Tabs defaultValue="desks">
        <Tabs.List>
          <Tabs.Tab value="desks" leftSection={<IconKeyboard size={16} />}>
            {t('config.tabs.desks')}
          </Tabs.Tab>
          <Tabs.Tab value="templates" leftSection={<IconTemplate size={16} />}>
            {t('config.tabs.templates')}
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="desks" pt="md">
          <Stack>
            <Select
              label={t('config.cashDesk')}
              placeholder={t('config.cashDeskPlaceholder')}
              searchable
              data={cashDesks.map((cashDesk) => ({
                value: String(cashDesk.id),
                label: `${cashDesk.branch_name} — ${cashDesk.name}`,
              }))}
              value={deskId}
              onChange={setDeskId}
              w={420}
            />

            {!deskId ? (
              <Text c="dimmed">{t('config.cashDeskPrompt')}</Text>
            ) : !deskConfig ? (
              <Loader size="sm" />
            ) : (
              <Card withBorder padding="md">
                <Stack>
                  <Group>
                    <Text fw={500}>{t('config.effective')}</Text>
                    <Badge color={sourceColor(deskConfig.source)} variant="light">
                      {sourceLabel(deskConfig.source, deskConfig.template_branch_id)}
                    </Badge>
                  </Group>

                  {deskEditing ? (
                    <>
                      <OperationsChecklist
                        operations={operations}
                        value={deskDraft}
                        onChange={setDeskDraft}
                      />
                      <Group>
                        <Button
                          leftSection={<IconDeviceFloppy size={16} />}
                          loading={deskSaving}
                          onClick={() => void saveDesk()}
                        >
                          {t('common.save')}
                        </Button>
                        <Button variant="default" onClick={() => setDeskEditing(false)}>
                          {t('common.cancel')}
                        </Button>
                      </Group>
                    </>
                  ) : (
                    <>
                      <OperationBadges operations={deskConfig.operations} />
                      <Group>
                        <Button
                          variant="light"
                          leftSection={<IconKeyboard size={16} />}
                          onClick={() => {
                            setDeskDraft(deskConfig.operations.map((operation) => operation.code))
                            setDeskEditing(true)
                          }}
                        >
                          {t('config.configureIndividually')}
                        </Button>
                        {deskConfig.source === 'own' && (
                          <Button
                            variant="default"
                            leftSection={<IconReload size={16} />}
                            loading={deskSaving}
                            onClick={() => void resetDesk()}
                          >
                            {t('config.removeOwn')}
                          </Button>
                        )}
                      </Group>
                    </>
                  )}
                </Stack>
              </Card>
            )}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="templates" pt="md">
          <Stack>
            {!canManageBank && (
              <Alert color="blue" icon={<IconAlertTriangle size={16} />}>
                {t('config.bank.readonly')}
              </Alert>
            )}

            <Card withBorder padding="md">
              <Stack>
                <Group justify="space-between">
                  <Text fw={500}>{t('config.bank.title')}</Text>
                  {bankTemplate && (
                    <Badge color={bankTemplate.defined ? 'teal' : 'red'} variant="light">
                      {bankTemplate.defined ? t('config.bank.defined') : t('config.bank.undefined')}
                    </Badge>
                  )}
                </Group>
                <Text size="sm" c="dimmed">
                  {t('config.bank.description')}
                </Text>
                <OperationsChecklist
                  operations={operations}
                  value={bankDraft}
                  onChange={setBankDraft}
                  disabled={!canManageBank}
                />
                <Group>
                  <Button
                    leftSection={<IconDeviceFloppy size={16} />}
                    loading={bankSaving}
                    disabled={!canManageBank}
                    onClick={() => void saveBank()}
                  >
                    {t('common.save')}
                  </Button>
                  <Button
                    variant="default"
                    color="red"
                    leftSection={<IconTrash size={16} />}
                    loading={bankSaving}
                    disabled={!canManageBank || !bankTemplate?.defined}
                    onClick={() => void deleteBank()}
                  >
                    {t('config.deleteTemplate')}
                  </Button>
                </Group>
              </Stack>
            </Card>

            <Card withBorder padding="md">
              <Stack>
                <Text fw={500}>{t('config.branch.title')}</Text>
                <Select
                  label={t('config.branch.label')}
                  placeholder={t('config.branch.placeholder')}
                  searchable
                  data={branches.map((branch) => ({
                    value: String(branch.id),
                    label: branchesWithTemplate.has(branch.id)
                      ? t('config.branch.definedSuffix', { name: branch.name })
                      : branch.name,
                  }))}
                  value={branchId}
                  onChange={setBranchId}
                  w={420}
                />
                {branchId && branchTemplate && (
                  <>
                    <Text size="sm" c="dimmed">
                      {t('config.branch.description')}
                    </Text>
                    <OperationsChecklist
                      operations={operations}
                      value={branchDraft}
                      onChange={setBranchDraft}
                    />
                    <Group>
                      <Button
                        leftSection={<IconDeviceFloppy size={16} />}
                        loading={branchSaving}
                        onClick={() => void saveBranch()}
                      >
                        {t('common.save')}
                      </Button>
                      <Button
                        variant="default"
                        color="red"
                        leftSection={<IconTrash size={16} />}
                        loading={branchSaving}
                        disabled={!branchTemplate.defined}
                        onClick={() => void deleteBranch()}
                      >
                        {t('config.deleteTemplate')}
                      </Button>
                    </Group>
                  </>
                )}
              </Stack>
            </Card>
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  )
}
