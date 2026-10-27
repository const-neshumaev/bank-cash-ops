import { Alert, Button, Group, Loader, Modal, Stack, Text } from '@mantine/core'
import { IconAlertCircle, IconChevronLeft, IconChevronRight, IconDownload, IconPrinter } from '@tabler/icons-react'
import { renderAsync } from 'docx-preview'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'

import * as operationsApi from '../api/operations'
import type { PrintDocument } from '../api/operations'

interface PrintDocumentsModalProps {
  opened: boolean
  documents: PrintDocument[]
  onClose: () => void
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

/**
 * Shows the documents of one operation one by one and lets the cashier print
 * or download each of them. The Word file is rendered by `docx-preview`; the
 * print stylesheet prints only the document currently on screen.
 */
export function PrintDocumentsModal({ opened, documents, onClose }: PrintDocumentsModalProps) {
  const { t } = useTranslation('operations')
  const [index, setIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const blobRef = useRef<Blob | null>(null)

  const document = documents[index]

  useEffect(() => {
    if (!opened) {
      setIndex(0)
      blobRef.current = null
      return
    }
    setIndex(0)
  }, [opened, documents])

  useEffect(() => {
    if (!opened || !document) return
    let cancelled = false
    setLoading(true)
    setError(null)
    blobRef.current = null
    operationsApi
      .downloadPrintDocument(document.id)
      .then(async (blob) => {
        if (cancelled) return
        blobRef.current = blob
        const container = containerRef.current
        if (!container) return
        container.innerHTML = ''
        await renderAsync(blob, container, container, {
          inWrapper: true,
          breakPages: true,
          ignoreWidth: false,
          ignoreHeight: false,
        })
      })
      .catch((downloadError) => {
        if (!cancelled) setError(extractErrorMessage(downloadError))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [opened, document])

  const printCurrent = () => {
    window.print()
  }

  const downloadCurrent = () => {
    if (!document || !blobRef.current) return
    saveBlob(blobRef.current, document.file_name)
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t('workplace.print.title')}
      size="xl"
      closeOnClickOutside={false}
    >
      <style>{`
        @media print {
          @page { margin: 10mm; }
          body * { visibility: hidden !important; }
          #bco-print-area, #bco-print-area * { visibility: visible !important; }
          #bco-print-area {
            position: absolute; left: 0; top: 0; width: 100%;
            max-height: none !important; overflow: visible !important;
            background: #fff !important; padding: 0 !important;
          }
          .mantine-Modal-content, .mantine-Modal-body, .mantine-Modal-inner {
            overflow: visible !important;
            max-height: none !important;
          }
        }
      `}</style>

      {documents.length === 0 || !document ? (
        <Text size="sm" c="dimmed">
          {t('workplace.print.empty')}
        </Text>
      ) : (
        <Stack>
          <Group justify="space-between">
            <Stack gap={0}>
              <Text fw={500}>{document.document_type_name}</Text>
              <Text size="xs" c="dimmed">
                {document.template_name}
              </Text>
              <Text size="xs" c="dimmed">
                {document.number === null
                  ? t('workplace.print.documentWithoutNumber', {
                      index: index + 1,
                      total: documents.length,
                    })
                  : t('workplace.print.document', {
                      number: document.number,
                      index: index + 1,
                      total: documents.length,
                    })}
              </Text>
            </Stack>
            <Group gap="xs">
              <Button
                variant="default"
                size="compact-sm"
                leftSection={<IconChevronLeft size={16} />}
                disabled={index === 0}
                onClick={() => setIndex((value) => Math.max(0, value - 1))}
              >
                {t('workplace.print.previous')}
              </Button>
              <Button
                variant="default"
                size="compact-sm"
                rightSection={<IconChevronRight size={16} />}
                disabled={index >= documents.length - 1}
                onClick={() => setIndex((value) => Math.min(documents.length - 1, value + 1))}
              >
                {t('workplace.print.next')}
              </Button>
            </Group>
          </Group>

          {error ? (
            <Alert color="red" icon={<IconAlertCircle size={16} />}>
              {error}
            </Alert>
          ) : loading ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : null}

          <div
            id="bco-print-area"
            ref={containerRef}
            style={{ overflow: 'auto', maxHeight: '60vh', background: '#f5f5f5', padding: 8 }}
          />

          <Group justify="flex-end">
            <Button
              variant="default"
              leftSection={<IconDownload size={16} />}
              disabled={!blobRef.current}
              onClick={downloadCurrent}
            >
              {t('workplace.print.download')}
            </Button>
            <Button leftSection={<IconPrinter size={16} />} onClick={printCurrent} disabled={loading}>
              {t('workplace.print.print')}
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  )
}
