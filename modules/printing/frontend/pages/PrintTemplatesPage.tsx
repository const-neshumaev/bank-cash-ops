import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  FileButton,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconDownload, IconUpload, IconVariable } from '@tabler/icons-react'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import { useAuth } from '@app/auth/AuthContext'

import * as printingApi from '../api/printing'
import type { PrintTemplate } from '../api/printing'

const MANAGE_PERMISSION = 'printing.templates.manage'

interface TemplateGroup {
  code: string
  name: string
  templates: PrintTemplate[]
}

function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function formatSize(size: number | null): string {
  if (!size) return '—'
  return `${Math.max(1, Math.round(size / 1024))} KB`
}

export function PrintTemplatesPage() {
  const { t } = useTranslation('printing')
  const { hasPermission } = useAuth()
  const canManage = hasPermission(MANAGE_PERMISSION)

  const [templates, setTemplates] = useState<PrintTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [variables, setVariables] = useState<PrintTemplate | null>(null)

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
      setTemplates(await printingApi.listPrintTemplates())
    } catch (error) {
      notifyError(error)
    } finally {
      setLoading(false)
    }
  }, [notifyError])

  useEffect(() => {
    void load()
  }, [load])

  const groups = useMemo<TemplateGroup[]>(() => {
    const byCode = new Map<string, TemplateGroup>()
    for (const template of templates) {
      const group = byCode.get(template.document_type) ?? {
        code: template.document_type,
        name: template.document_type_name || template.document_type,
        templates: [],
      }
      group.templates.push(template)
      byCode.set(template.document_type, group)
    }
    return [...byCode.values()]
  }, [templates])

  const download = async (template: PrintTemplate) => {
    setDownloading(template.code)
    try {
      const blob = await printingApi.downloadPrintTemplate(template.code)
      saveBlob(blob, template.file_name || `${template.code}.docx`)
    } catch (error) {
      notifyError(error)
    } finally {
      setDownloading(null)
    }
  }

  const upload = async (template: PrintTemplate, file: File) => {
    setUploading(template.code)
    try {
      const updated = await printingApi.uploadPrintTemplate(template.code, file)
      setTemplates((current) =>
        current.map((item) => (item.code === updated.code ? updated : item)),
      )
      notifications.show({ color: 'green', message: t('templates.uploaded') })
    } catch (error) {
      notifyError(error)
    } finally {
      setUploading(null)
    }
  }

  if (loading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    )
  }

  return (
    <Stack>
      <Title order={3}>{t('templates.title')}</Title>
      <Text size="sm" c="dimmed">
        {t('templates.hint')}
      </Text>

      {groups.length === 0 ? (
        <Alert color="blue" icon={<IconAlertCircle size={16} />}>
          {t('templates.empty')}
        </Alert>
      ) : (
        groups.map((group) => (
          <Card key={group.code} withBorder padding="lg" radius="md">
            <Stack>
              <Group justify="space-between">
                <Stack gap={0}>
                  <Text fw={500}>{group.name}</Text>
                  <Text size="xs" c="dimmed">
                    {group.code}
                  </Text>
                </Stack>
                <Badge variant="light">{t('templates.templatesCount', { count: group.templates.length })}</Badge>
              </Group>

              <Table striped withTableBorder>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('templates.columns.name')}</Table.Th>
                    <Table.Th>{t('templates.columns.code')}</Table.Th>
                    <Table.Th>{t('templates.columns.file')}</Table.Th>
                    <Table.Th>{t('templates.columns.updatedAt')}</Table.Th>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {group.templates.map((template) => (
                    <Table.Tr key={template.code}>
                      <Table.Td>
                        <Stack gap={2}>
                          <Group gap="xs">
                            <Text fw={500}>{template.name}</Text>
                            {!template.is_active && (
                              <Badge color="gray" variant="light">
                                {t('templates.inactive')}
                              </Badge>
                            )}
                          </Group>
                          {template.description && (
                            <Text size="xs" c="dimmed">
                              {template.description}
                            </Text>
                          )}
                          {template.last_error && (
                            <Alert color="red" p="xs" icon={<IconAlertCircle size={14} />}>
                              <Text size="xs">{template.last_error}</Text>
                            </Alert>
                          )}
                        </Stack>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{template.code}</Text>
                      </Table.Td>
                      <Table.Td>
                        {template.has_file ? (
                          <Stack gap={2}>
                            <Text size="sm">{template.file_name}</Text>
                            <Text size="xs" c="dimmed">
                              {formatSize(template.file_size)}
                            </Text>
                          </Stack>
                        ) : (
                          <Text size="sm" c="dimmed">
                            {t('templates.noFile')}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        {template.file_updated_at
                          ? dayjs(template.file_updated_at).format('DD.MM.YYYY HH:mm')
                          : '—'}
                      </Table.Td>
                      <Table.Td>
                        <Group gap={4} justify="flex-end" wrap="nowrap">
                          <Button
                            size="compact-sm"
                            variant="subtle"
                            leftSection={<IconVariable size={16} />}
                            onClick={() => setVariables(template)}
                          >
                            {t('templates.variables')}
                          </Button>
                          <Button
                            size="compact-sm"
                            variant="subtle"
                            leftSection={<IconDownload size={16} />}
                            disabled={!template.has_file}
                            loading={downloading === template.code}
                            onClick={() => void download(template)}
                          >
                            {t('templates.download')}
                          </Button>
                          {canManage && (
                            <FileButton
                              accept=".docx"
                              onChange={(file) => file && void upload(template, file)}
                            >
                              {(props) => (
                                <Button
                                  {...props}
                                  size="compact-sm"
                                  variant="subtle"
                                  leftSection={<IconUpload size={16} />}
                                  loading={uploading === template.code}
                                >
                                  {t('templates.upload')}
                                </Button>
                              )}
                            </FileButton>
                          )}
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Stack>
          </Card>
        ))
      )}

      <Modal
        opened={Boolean(variables)}
        onClose={() => setVariables(null)}
        title={variables?.name ?? t('templates.variables')}
        size="lg"
      >
        <Stack>
          <Text size="sm" c="dimmed">
            {t('templates.variablesHint')}
          </Text>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('templates.columns.variable')}</Table.Th>
                <Table.Th>{t('templates.columns.description')}</Table.Th>
                <Table.Th>{t('templates.columns.example')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(variables?.variables ?? []).map((variable) => (
                <Table.Tr key={variable.code}>
                  <Table.Td>
                    <Text size="sm" ff="monospace">{`{{ ${variable.code} }}`}</Text>
                  </Table.Td>
                  <Table.Td>{variable.description}</Table.Td>
                  <Table.Td>{variable.example || '—'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      </Modal>
    </Stack>
  )
}
