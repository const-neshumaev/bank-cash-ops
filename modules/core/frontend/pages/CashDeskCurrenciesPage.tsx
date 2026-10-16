import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Select,
  Stack,
  Table,
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
  IconX,
} from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import type { Branch, CashDesk } from '@app/api/types'
import { useAuth } from '@app/auth/AuthContext'

import { listAllBranches } from '../api/branches'
import { listAllCashDesks } from '../api/cashDesks'
import * as currencyApi from '../api/currencyConfig'
import type { CashDeskCurrencies, ConfigSource, CurrencyOption, CurrencyTemplate } from '../api/currencyConfig'

const BANK_PERMISSION = 'core.currencies.config.manage'

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

interface CurrencyListEditorProps {
  currencies: CurrencyOption[]
  value: string[]
  onChange: (value: string[]) => void
  disabled?: boolean
}

/**
 * A grid of the selected currencies with an "add" picker.
 *
 * The catalogue holds the whole ISO 4217 list, so a checkbox per currency is
 * unwieldy: the editor shows only what is selected and offers a searchable
 * picker over the currencies that are not selected yet.
 */
function CurrencyListEditor({ currencies, value, onChange, disabled }: CurrencyListEditorProps) {
  const { t } = useTranslation('core')
  const byCode = new Map(currencies.map((currency) => [currency.code, currency]))
  const selected = new Set(value)
  const options = currencies
    .filter((currency) => !selected.has(currency.code))
    .map((currency) => ({ value: currency.code, label: `${currency.code} — ${currency.name}` }))

  const remove = (code: string) => onChange(value.filter((item) => item !== code))

  return (
    <Stack gap="xs">
      {value.length === 0 ? (
        <Text c="dimmed" size="sm">
          {t('cashDeskCurrencies.noCurrenciesSelected')}
        </Text>
      ) : (
        <Table withTableBorder>
          <Table.Tbody>
            {value.map((code) => (
              <Table.Tr key={code}>
                <Table.Td w={90}>
                  <Text fw={500}>{code}</Text>
                </Table.Td>
                <Table.Td>{byCode.get(code)?.name ?? code}</Table.Td>
                <Table.Td w={48}>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    disabled={disabled}
                    aria-label={t('common.delete')}
                    onClick={() => remove(code)}
                  >
                    <IconX size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      <Select
        placeholder={t('cashDeskCurrencies.addCurrency')}
        searchable
        nothingFoundMessage={t('cashDeskCurrencies.noCurrenciesToAdd')}
        data={options}
        value={null}
        onChange={(code) => {
          if (code && !selected.has(code)) onChange([...value, code])
        }}
        disabled={disabled || options.length === 0}
        w={420}
      />
    </Stack>
  )
}

function CurrencyBadges({ currencies }: { currencies: CurrencyOption[] }) {
  const { t } = useTranslation('core')
  if (currencies.length === 0) {
    return (
      <Text c="dimmed" size="sm">
        {t('cashDeskCurrencies.currencyNotAllowed')}
      </Text>
    )
  }
  return (
    <Group gap={6}>
      {currencies.map((currency) => (
        <Badge key={currency.code} variant="light">
          {currency.code} — {currency.name}
        </Badge>
      ))}
    </Group>
  )
}

export function CashDeskCurrenciesPage() {
  const { t } = useTranslation('core')
  const { hasPermission } = useAuth()
  const canManageBank = hasPermission(BANK_PERMISSION)

  const [currencies, setCurrencies] = useState<CurrencyOption[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [cashDesks, setCashDesks] = useState<CashDesk[]>([])
  const [templates, setTemplates] = useState<currencyApi.CurrencyTemplateSummary[]>([])

  const [deskId, setDeskId] = useState<string | null>(null)
  const [deskConfig, setDeskConfig] = useState<CashDeskCurrencies | null>(null)
  const [deskEditing, setDeskEditing] = useState(false)
  const [deskDraft, setDeskDraft] = useState<string[]>([])
  const [deskSaving, setDeskSaving] = useState(false)

  const [bankTemplate, setBankTemplate] = useState<CurrencyTemplate | null>(null)
  const [bankDraft, setBankDraft] = useState<string[]>([])
  const [bankSaving, setBankSaving] = useState(false)

  const [branchId, setBranchId] = useState<string | null>(null)
  const [branchTemplate, setBranchTemplate] = useState<CurrencyTemplate | null>(null)
  const [branchDraft, setBranchDraft] = useState<string[]>([])
  const [branchSaving, setBranchSaving] = useState(false)

  const branchName = useCallback(
    (id: number) => branches.find((branch) => branch.id === id)?.name ?? `#${id}`,
    [branches],
  )

  const sourceLabel = (source: ConfigSource, templateBranchId: number | null): string => {
    switch (source) {
      case 'own':
        return t('cashDeskCurrencies.source.own')
      case 'branch':
        return t('cashDeskCurrencies.source.branch', {
          branch: templateBranchId ? branchName(templateBranchId) : '',
        })
      case 'bank':
        return t('cashDeskCurrencies.source.bank')
      default:
        return t('cashDeskCurrencies.source.none')
    }
  }

  const branchesWithTemplate = useMemo(
    () => new Set(templates.map((template) => template.branch_id).filter((id): id is number => id !== null)),
    [templates],
  )

  const notifyError = (error: unknown) =>
    notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })

  const reloadTemplates = useCallback(async () => {
    try {
      setTemplates(await currencyApi.listCurrencyTemplates())
    } catch (error) {
      notifyError(error)
    }
  }, [])

  const reloadBankTemplate = useCallback(async () => {
    try {
      const template = await currencyApi.fetchBankCurrencyTemplate()
      setBankTemplate(template)
      setBankDraft(template.currencies.map((currency) => currency.code))
    } catch (error) {
      notifyError(error)
    }
  }, [])

  useEffect(() => {
    void Promise.all([
      currencyApi.listActiveCurrencies(),
      listAllBranches(),
      listAllCashDesks(),
    ])
      .then(([currencyList, branchList, deskList]) => {
        setCurrencies(currencyList)
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
    void currencyApi
      .fetchCashDeskCurrencies(Number(deskId))
      .then((config) => {
        setDeskConfig(config)
        setDeskDraft(config.currencies.map((currency) => currency.code))
      })
      .catch(notifyError)
  }, [deskId])

  useEffect(() => {
    if (!branchId) {
      setBranchTemplate(null)
      return
    }
    void currencyApi
      .fetchBranchCurrencyTemplate(Number(branchId))
      .then((template) => {
        setBranchTemplate(template)
        setBranchDraft(template.currencies.map((currency) => currency.code))
      })
      .catch(notifyError)
  }, [branchId])

  const saveDesk = async () => {
    if (!deskId) return
    setDeskSaving(true)
    try {
      const config = await currencyApi.setCashDeskCurrencies(Number(deskId), deskDraft)
      setDeskConfig(config)
      setDeskEditing(false)
      notifications.show({ color: 'green', message: t('cashDeskCurrencies.deskSaved') })
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
      const config = await currencyApi.setCashDeskCurrencies(Number(deskId), [])
      setDeskConfig(config)
      setDeskDraft(config.currencies.map((currency) => currency.code))
      setDeskEditing(false)
      notifications.show({ color: 'green', message: t('cashDeskCurrencies.deskReset') })
    } catch (error) {
      notifyError(error)
    } finally {
      setDeskSaving(false)
    }
  }

  const saveBank = async () => {
    setBankSaving(true)
    try {
      const template = await currencyApi.setBankCurrencyTemplate(bankDraft)
      setBankTemplate(template)
      await reloadTemplates()
      notifications.show({ color: 'green', message: t('cashDeskCurrencies.bankSaved') })
    } catch (error) {
      notifyError(error)
    } finally {
      setBankSaving(false)
    }
  }

  const deleteBank = async () => {
    setBankSaving(true)
    try {
      await currencyApi.deleteBankCurrencyTemplate()
      await reloadBankTemplate()
      await reloadTemplates()
      notifications.show({ color: 'green', message: t('cashDeskCurrencies.bankDeleted') })
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
      const template = await currencyApi.setBranchCurrencyTemplate(Number(branchId), branchDraft)
      setBranchTemplate(template)
      await reloadTemplates()
      notifications.show({ color: 'green', message: t('cashDeskCurrencies.branchSaved') })
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
      await currencyApi.deleteBranchCurrencyTemplate(Number(branchId))
      await reloadTemplates()
      setBranchTemplate({ branch_id: Number(branchId), defined: false, currencies: [] })
      setBranchDraft([])
      notifications.show({ color: 'green', message: t('cashDeskCurrencies.branchDeleted') })
    } catch (error) {
      notifyError(error)
    } finally {
      setBranchSaving(false)
    }
  }

  return (
    <Stack>
      <Title order={3}>{t('cashDeskCurrencies.title')}</Title>

      <Tabs defaultValue="desks">
        <Tabs.List>
          <Tabs.Tab value="desks" leftSection={<IconKeyboard size={16} />}>
            {t('cashDeskCurrencies.tabDesks')}
          </Tabs.Tab>
          <Tabs.Tab value="templates" leftSection={<IconTemplate size={16} />}>
            {t('cashDeskCurrencies.tabTemplates')}
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="desks" pt="md">
          <Stack>
            <Select
              label={t('cashDeskCurrencies.cashDesk')}
              placeholder={t('cashDeskCurrencies.selectCashDesk')}
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
              <Text c="dimmed">{t('cashDeskCurrencies.selectCashDeskHint')}</Text>
            ) : !deskConfig ? (
              <Loader size="sm" />
            ) : (
              <Card withBorder padding="md">
                <Stack>
                  <Group>
                    <Text fw={500}>{t('cashDeskCurrencies.effectiveCurrencies')}</Text>
                    <Badge color={sourceColor(deskConfig.source)} variant="light">
                      {sourceLabel(deskConfig.source, deskConfig.template_branch_id)}
                    </Badge>
                  </Group>

                  {deskEditing ? (
                    <>
                      <CurrencyListEditor
                        currencies={currencies}
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
                      <CurrencyBadges currencies={deskConfig.currencies} />
                      <Group>
                        <Button
                          variant="light"
                          leftSection={<IconKeyboard size={16} />}
                          onClick={() => {
                            setDeskDraft(deskConfig.currencies.map((currency) => currency.code))
                            setDeskEditing(true)
                          }}
                        >
                          {t('cashDeskCurrencies.configureIndividually')}
                        </Button>
                        {deskConfig.source === 'own' && (
                          <Button
                            variant="default"
                            leftSection={<IconReload size={16} />}
                            loading={deskSaving}
                            onClick={() => void resetDesk()}
                          >
                            {t('cashDeskCurrencies.resetOwn')}
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
                {t('cashDeskCurrencies.bankTemplateAlert')}
              </Alert>
            )}

            <Card withBorder padding="md">
              <Stack>
                <Group justify="space-between">
                  <Text fw={500}>{t('cashDeskCurrencies.bankTemplate')}</Text>
                  {bankTemplate && (
                    <Badge color={bankTemplate.defined ? 'teal' : 'red'} variant="light">
                      {bankTemplate.defined
                        ? t('cashDeskCurrencies.defined')
                        : t('cashDeskCurrencies.notDefined')}
                    </Badge>
                  )}
                </Group>
                <Text size="sm" c="dimmed">
                  {t('cashDeskCurrencies.bankTemplateHint')}
                </Text>
                <CurrencyListEditor
                  currencies={currencies}
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
                    {t('cashDeskCurrencies.deleteTemplate')}
                  </Button>
                </Group>
              </Stack>
            </Card>

            <Card withBorder padding="md">
              <Stack>
                <Text fw={500}>{t('cashDeskCurrencies.branchTemplate')}</Text>
                <Select
                  label={t('cashDeskCurrencies.branch')}
                  placeholder={t('cashDeskCurrencies.selectBranch')}
                  searchable
                  data={branches.map((branch) => ({
                    value: String(branch.id),
                    label: branchesWithTemplate.has(branch.id)
                      ? t('cashDeskCurrencies.branchWithTemplate', { name: branch.name })
                      : branch.name,
                  }))}
                  value={branchId}
                  onChange={setBranchId}
                  w={420}
                />
                {branchId && branchTemplate && (
                  <>
                    <Text size="sm" c="dimmed">
                      {t('cashDeskCurrencies.branchTemplateHint')}
                    </Text>
                    <CurrencyListEditor
                      currencies={currencies}
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
                        {t('cashDeskCurrencies.deleteTemplate')}
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
