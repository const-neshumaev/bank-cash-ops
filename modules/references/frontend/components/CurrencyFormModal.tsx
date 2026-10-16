import { Button, Checkbox, Group, Modal, NumberInput, Stack, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'

import * as currenciesApi from '../api/currencies'

interface CurrencyFormModalProps {
  opened: boolean
  currency: currenciesApi.Currency | null
  onClose: () => void
  onSaved: () => void
}

interface FormValues {
  code: string
  numeric_code: string
  name: string
  symbol: string
  minor_units: number
  is_active: boolean
}

const EMPTY_VALUES: FormValues = {
  code: '',
  numeric_code: '',
  name: '',
  symbol: '',
  minor_units: 2,
  is_active: true,
}

export function CurrencyFormModal({ opened, currency, onClose, onSaved }: CurrencyFormModalProps) {
  const { t } = useTranslation('references')
  const isEdit = Boolean(currency)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<FormValues>({
    initialValues: EMPTY_VALUES,
    validate: {
      code: (value) => (value.trim() ? null : t('validation.code')),
      name: (value) => (value.trim() ? null : t('validation.name')),
    },
  })

  useEffect(() => {
    if (!opened) return
    if (currency) {
      form.setValues({
        code: currency.code,
        numeric_code: currency.numeric_code,
        name: currency.name,
        symbol: currency.symbol,
        minor_units: currency.minor_units,
        is_active: currency.is_active,
      })
    } else {
      form.setValues(EMPTY_VALUES)
    }
    form.resetDirty()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, currency])

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    try {
      const payload = {
        code: values.code.trim().toUpperCase(),
        numeric_code: values.numeric_code.trim(),
        name: values.name.trim(),
        symbol: values.symbol.trim(),
        minor_units: values.minor_units,
        is_active: values.is_active,
      }
      if (currency) {
        await currenciesApi.updateCurrency(currency.code, payload)
        notifications.show({ color: 'green', message: t('currencies.updated') })
      } else {
        await currenciesApi.createCurrency(payload)
        notifications.show({ color: 'green', message: t('currencies.created') })
      }
      onSaved()
      onClose()
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setSubmitting(false)
    }
  })

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={isEdit ? t('currencies.editTitle') : t('currencies.createTitle')}
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput
            label={t('currencies.form.code')}
            required
            disabled={isEdit}
            {...form.getInputProps('code')}
          />
          <TextInput
            label={t('currencies.form.numericCode')}
            maxLength={3}
            {...form.getInputProps('numeric_code')}
          />
          <TextInput label={t('currencies.form.name')} required {...form.getInputProps('name')} />
          <TextInput label={t('currencies.form.symbol')} {...form.getInputProps('symbol')} />
          <NumberInput
            label={t('currencies.form.minorUnits')}
            min={0}
            clampBehavior="strict"
            {...form.getInputProps('minor_units')}
          />
          <Checkbox
            label={t('currencies.form.active')}
            {...form.getInputProps('is_active', { type: 'checkbox' })}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={submitting}>
              {t('common.save')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
