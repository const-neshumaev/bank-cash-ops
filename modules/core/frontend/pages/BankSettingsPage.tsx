import { Alert, Button, Card, Group, Loader, Select, Stack, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconDeviceFloppy, IconInfoCircle } from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'

import * as bankSettingsApi from '../api/bankSettings'
import type { ConversionMode } from '../api/bankSettings'
import { listActiveCurrencies } from '../api/currencyConfig'
import type { CurrencyOption } from '../api/currencyConfig'

export function BankSettingsPage() {
  const { t } = useTranslation('core')
  const [baseCurrency, setBaseCurrency] = useState<string | null>(null)
  const [conversionMode, setConversionMode] = useState<ConversionMode>('via_base')
  const [currencies, setCurrencies] = useState<CurrencyOption[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [settings, currencyRows] = await Promise.all([
        bankSettingsApi.fetchBankSettings(),
        listActiveCurrencies(),
      ])
      setBaseCurrency(settings.base_currency)
      setConversionMode(settings.conversion_mode)
      setCurrencies(currencyRows)
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  const options = useMemo(
    () =>
      currencies.map((currency) => ({
        value: currency.code,
        label: `${currency.code} — ${currency.name}`,
      })),
    [currencies],
  )

  const conversionOptions: { value: ConversionMode; label: string }[] = [
    { value: 'via_base', label: t('bankSettings.conversionModes.via_base') },
    { value: 'direct', label: t('bankSettings.conversionModes.direct') },
  ]

  const save = async () => {
    if (!baseCurrency) return
    setSaving(true)
    try {
      await bankSettingsApi.updateBankSettings({
        base_currency: baseCurrency,
        conversion_mode: conversionMode,
      })
      notifications.show({ color: 'green', message: t('bankSettings.saved') })
      await load()
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Stack>
      <Title order={3}>{t('bankSettings.title')}</Title>

      <Alert color="blue" variant="light" icon={<IconInfoCircle size={18} />}>
        {t('bankSettings.baseCurrencyHint')}
      </Alert>

      <Card withBorder padding="lg" radius="md">
        {loading ? (
          <Group justify="center" py="md">
            <Loader size="sm" />
          </Group>
        ) : (
          <Stack maw={480}>
            <Select
              label={t('bankSettings.baseCurrency')}
              data={options}
              searchable
              value={baseCurrency}
              onChange={setBaseCurrency}
              allowDeselect={false}
            />
            <Text size="xs" c="dimmed">
              {t('bankSettings.baseCurrencyReadonlyHint')}
            </Text>
            <Select
              label={t('bankSettings.conversionMode')}
              description={t('bankSettings.conversionModeHint')}
              data={conversionOptions}
              value={conversionMode}
              onChange={(value) => setConversionMode((value as ConversionMode) ?? 'via_base')}
              allowDeselect={false}
            />
            <Text size="xs" c="dimmed">
              {conversionMode === 'direct'
                ? t('bankSettings.conversionModeDirectHint')
                : t('bankSettings.conversionModeViaBaseHint')}
            </Text>
            <Group justify="flex-end">
              <Button
                leftSection={<IconDeviceFloppy size={16} />}
                loading={saving}
                onClick={() => void save()}
              >
                {t('common.save')}
              </Button>
            </Group>
          </Stack>
        )}
      </Card>
    </Stack>
  )
}
