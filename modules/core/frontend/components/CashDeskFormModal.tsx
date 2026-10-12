import { Button, Group, Modal, Select, Stack, Switch, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { Branch, CashDesk } from '@app/api/types'

import * as branchesApi from '../api/branches'
import * as cashDesksApi from '../api/cashDesks'

interface CashDeskFormModalProps {
  opened: boolean
  cashDesk: CashDesk | null
  onClose: () => void
  onSaved: () => void
}

interface FormValues {
  branch: string | null
  name: string
  code: string
  mac_address: string
  hostname: string
  is_active: boolean
}

const EMPTY_VALUES: FormValues = {
  branch: null,
  name: '',
  code: '',
  mac_address: '',
  hostname: '',
  is_active: true,
}

const MAC_PATTERN = /^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/

export function CashDeskFormModal({ opened, cashDesk, onClose, onSaved }: CashDeskFormModalProps) {
  const isEdit = Boolean(cashDesk)
  const [submitting, setSubmitting] = useState(false)
  const [branches, setBranches] = useState<Branch[]>([])

  const form = useForm<FormValues>({
    initialValues: EMPTY_VALUES,
    validate: {
      name: (value) => (value.trim() ? null : 'Укажите название'),
      code: (value) => (value.trim() ? null : 'Укажите код'),
      branch: (value) => (value ? null : 'Выберите отделение'),
      mac_address: (value) =>
        !value.trim() || MAC_PATTERN.test(value.trim())
          ? null
          : 'MAC-адрес в формате AA:BB:CC:DD:EE:FF',
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
    if (cashDesk) {
      form.setValues({
        branch: String(cashDesk.branch),
        name: cashDesk.name,
        code: cashDesk.code,
        mac_address: cashDesk.mac_address ?? '',
        hostname: cashDesk.hostname,
        is_active: cashDesk.is_active,
      })
    } else {
      form.setValues(EMPTY_VALUES)
    }
    form.resetDirty()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, cashDesk])

  const branchOptions = branches.map((branch) => ({
    value: String(branch.id),
    label: `${branch.name} (${branch.code})`,
  }))

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    try {
      const payload = {
        branch: Number(values.branch),
        name: values.name.trim(),
        code: values.code.trim(),
        mac_address: values.mac_address.trim() || null,
        hostname: values.hostname.trim(),
        is_active: values.is_active,
      }
      if (cashDesk) {
        await cashDesksApi.updateCashDesk(cashDesk.id, payload)
        notifications.show({ color: 'green', message: 'Касса обновлена' })
      } else {
        await cashDesksApi.createCashDesk(payload)
        notifications.show({ color: 'green', message: 'Касса создана' })
      }
      onSaved()
      onClose()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setSubmitting(false)
    }
  })

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={isEdit ? 'Редактирование кассы' : 'Новая касса'}
      size="lg"
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <Select
            label="Отделение"
            data={branchOptions}
            searchable
            required
            {...form.getInputProps('branch')}
          />
          <Group grow align="flex-start">
            <TextInput label="Название" required {...form.getInputProps('name')} />
            <TextInput label="Код" required {...form.getInputProps('code')} />
          </Group>
          <TextInput
            label="MAC-адрес"
            placeholder="AA:BB:CC:DD:EE:FF"
            description="Сетевой адрес рабочего компьютера"
            {...form.getInputProps('mac_address')}
          />
          <TextInput label="Имя компьютера" {...form.getInputProps('hostname')} />
          <Switch label="Активна" {...form.getInputProps('is_active', { type: 'checkbox' })} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" loading={submitting}>
              Сохранить
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
