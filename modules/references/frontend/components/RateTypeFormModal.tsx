import {
  Button,
  Checkbox,
  Group,
  Modal,
  NumberInput,
  Select,
  Stack,
  Switch,
  TextInput,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'

import * as rateTypesApi from '../api/rateTypes'
import type { RatePrinciple, RateValidity } from '../api/rateTypes'

interface RateTypeFormModalProps {
  opened: boolean
  rateType: rateTypesApi.RateType | null
  onClose: () => void
  onSaved: () => void
}

interface FormValues {
  code: string
  name: string
  principle: RatePrinciple
  validity: RateValidity
  daily_required: boolean
  is_active: boolean
  order: number
}

function defaultsFor(principle: RatePrinciple): Pick<FormValues, 'validity' | 'daily_required'> {
  if (principle === 'official') {
    return { validity: 'calendar_day', daily_required: true }
  }
  return { validity: 'since_set', daily_required: false }
}

const EMPTY_VALUES: FormValues = {
  code: '',
  name: '',
  principle: 'official',
  ...defaultsFor('official'),
  is_active: true,
  order: 0,
}

export function RateTypeFormModal({ opened, rateType, onClose, onSaved }: RateTypeFormModalProps) {
  const { t } = useTranslation('references')
  const isEdit = Boolean(rateType)
  const [submitting, setSubmitting] = useState(false)

  const principleOptions: { value: RatePrinciple; label: string }[] = [
    { value: 'official', label: t('rateTypes.principle.official') },
    { value: 'buy', label: t('rateTypes.principle.buy') },
    { value: 'sell', label: t('rateTypes.principle.sell') },
    { value: 'conversion', label: t('rateTypes.principle.conversion') },
  ]

  const validityOptions: { value: RateValidity; label: string }[] = [
    { value: 'calendar_day', label: t('rateTypes.validity.calendar_day') },
    { value: 'since_set', label: t('rateTypes.validity.since_set') },
  ]

  const form = useForm<FormValues>({
    initialValues: EMPTY_VALUES,
    validate: {
      code: (value) => (value.trim() ? null : t('validation.code')),
      name: (value) => (value.trim() ? null : t('validation.name')),
    },
  })

  useEffect(() => {
    if (!opened) return
    if (rateType) {
      form.setValues({
        code: rateType.code,
        name: rateType.name,
        principle: rateType.principle,
        validity: rateType.validity,
        daily_required: rateType.daily_required,
        is_active: rateType.is_active,
        order: rateType.order,
      })
    } else {
      form.setValues(EMPTY_VALUES)
    }
    form.resetDirty()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, rateType])

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    try {
      const payload = {
        code: values.code.trim(),
        name: values.name.trim(),
        principle: values.principle,
        validity: values.validity,
        daily_required: values.daily_required,
        is_active: values.is_active,
        order: values.order,
      }
      if (rateType) {
        await rateTypesApi.updateRateType(rateType.id, payload)
        notifications.show({ color: 'green', message: t('rateTypes.updated') })
      } else {
        await rateTypesApi.createRateType(payload)
        notifications.show({ color: 'green', message: t('rateTypes.created') })
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
      title={isEdit ? t('rateTypes.editTitle') : t('rateTypes.createTitle')}
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput
            label={t('rateTypes.form.code')}
            required
            disabled={isEdit}
            {...form.getInputProps('code')}
          />
          <TextInput label={t('rateTypes.form.name')} required {...form.getInputProps('name')} />
          <Select
            label={t('rateTypes.form.principle')}
            data={principleOptions}
            allowDeselect={false}
            {...form.getInputProps('principle')}
            onChange={(value) => {
              const principle = (value as RatePrinciple) ?? 'official'
              form.setFieldValue('principle', principle)
              if (!isEdit) {
                form.setValues({ ...form.values, principle, ...defaultsFor(principle) })
              }
            }}
          />
          <Select
            label={t('rateTypes.form.validity')}
            description={t('rateTypes.form.validityHint')}
            data={validityOptions}
            allowDeselect={false}
            {...form.getInputProps('validity')}
          />
          <Switch
            label={t('rateTypes.form.dailyRequired')}
            description={t('rateTypes.form.dailyRequiredHint')}
            {...form.getInputProps('daily_required', { type: 'checkbox' })}
          />
          <NumberInput
            label={t('rateTypes.form.order')}
            min={0}
            clampBehavior="strict"
            {...form.getInputProps('order')}
          />
          <Checkbox
            label={t('rateTypes.form.active')}
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
