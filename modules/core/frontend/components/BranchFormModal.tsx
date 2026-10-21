import { Button, Group, Modal, Select, Stack, Switch, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import type { Branch } from '@app/api/types'

import * as branchesApi from '../api/branches'

interface BranchFormModalProps {
  opened: boolean
  branch: Branch | null
  onClose: () => void
  onSaved: () => void
}

interface FormValues {
  name: string
  code: string
  parent: string | null
  address: string
  phone: string
  is_head_office: boolean
  is_active: boolean
  uses_individual_rates: boolean
}

const EMPTY_VALUES: FormValues = {
  name: '',
  code: '',
  parent: null,
  address: '',
  phone: '',
  is_head_office: false,
  is_active: true,
  uses_individual_rates: false,
}

export function BranchFormModal({ opened, branch, onClose, onSaved }: BranchFormModalProps) {
  const { t } = useTranslation('core')
  const isEdit = Boolean(branch)
  const [submitting, setSubmitting] = useState(false)
  const [branches, setBranches] = useState<Branch[]>([])

  const form = useForm<FormValues>({
    initialValues: EMPTY_VALUES,
    validate: {
      name: (value) => (value.trim() ? null : t('validation.name')),
      parent: (value, values) =>
        values.is_head_office || value ? null : t('validation.parentBranch'),
    },
  })

  useEffect(() => {
    if (!opened) return
    void branchesApi
      .listAllBranches()
      .then(setBranches)
      .catch(() => setBranches([]))
  }, [opened])

  useEffect(() => {
    if (!opened) return
    if (branch) {
      form.setValues({
        name: branch.name,
        code: branch.code ?? '',
        parent: branch.parent ? String(branch.parent) : null,
        address: branch.address,
        phone: branch.phone,
        is_head_office: branch.is_head_office,
        is_active: branch.is_active,
        uses_individual_rates: branch.uses_individual_rates,
      })
    } else {
      form.setValues(EMPTY_VALUES)
    }
    form.resetDirty()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, branch])

  const isHeadOffice = form.values.is_head_office
  const parentOptions = branches
    .filter((item) => item.id !== branch?.id)
    .map((item) => ({
      value: String(item.id),
      label: item.code ? `${item.name} (${item.code})` : item.name,
    }))

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    try {
      const payload = {
        name: values.name.trim(),
        code: values.code.trim() || null,
        parent: values.is_head_office ? null : Number(values.parent),
        address: values.address.trim(),
        phone: values.phone.trim(),
        is_head_office: values.is_head_office,
        is_active: values.is_active,
        uses_individual_rates: values.uses_individual_rates,
      }
      if (branch) {
        await branchesApi.updateBranch(branch.id, payload)
        notifications.show({ color: 'green', message: t('branches.updated') })
      } else {
        await branchesApi.createBranch(payload)
        notifications.show({ color: 'green', message: t('branches.created') })
      }
      onSaved()
      onClose()
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
    } finally {
      setSubmitting(false)
    }
  })

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={isEdit ? t('branches.editTitle') : t('branches.createTitle')}
      size="lg"
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <Group grow align="flex-start">
            <TextInput label={t('branches.form.name')} required {...form.getInputProps('name')} />
            <TextInput
              label={t('branches.form.code')}
              description={t('branches.form.codeHint')}
              {...form.getInputProps('code')}
            />
          </Group>
          <Switch
            label={t('branches.form.headOffice')}
            {...form.getInputProps('is_head_office', { type: 'checkbox' })}
          />
          <Select
            label={t('branches.form.parent')}
            data={parentOptions}
            searchable
            clearable
            disabled={isHeadOffice}
            required={!isHeadOffice}
            {...form.getInputProps('parent')}
          />
          <Group grow align="flex-start">
            <TextInput label={t('branches.form.address')} {...form.getInputProps('address')} />
            <TextInput label={t('branches.form.phone')} {...form.getInputProps('phone')} />
          </Group>
          <Switch
            label={t('branches.form.individualRates')}
            description={t('branches.form.individualRatesHint')}
            {...form.getInputProps('uses_individual_rates', { type: 'checkbox' })}
          />
          <Switch
            label={t('branches.form.active')}
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
