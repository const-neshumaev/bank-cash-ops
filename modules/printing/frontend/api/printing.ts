import { api } from '@app/api/client'
import type { Paginated } from '@app/api/types'

export interface PrintVariable {
  code: string
  description: string
  example: string
}

export interface PrintTemplate {
  code: string
  name: string
  document_type: string
  document_type_name: string
  description: string
  provider: string
  file_name: string
  file_size: number | null
  file_updated_at: string | null
  has_file: boolean
  last_error: string
  last_error_at: string | null
  is_active: boolean
  variables: PrintVariable[]
}

export interface PrintDocumentType {
  code: string
  name: string
  description: string
  numbering_scope: string
  is_active: boolean
}

export interface PrintDocument {
  id: number
  document_type: string
  document_type_name: string
  template_code: string
  template_name: string
  operation_id: number
  operation_type_code: string
  cash_desk_id: number
  number: number | null
  file_name: string
  created_at: string
}

export async function listPrintTemplates(): Promise<PrintTemplate[]> {
  const { data } = await api.get<Paginated<PrintTemplate>>('/printing/templates/', {
    params: { page_size: 100, ordering: 'name' },
  })
  return data.results
}

export async function listPrintDocumentTypes(): Promise<PrintDocumentType[]> {
  const { data } = await api.get<Paginated<PrintDocumentType>>('/printing/document-types/', {
    params: { page_size: 100 },
  })
  return data.results
}

export async function downloadPrintTemplate(code: string): Promise<Blob> {
  const { data } = await api.get<Blob>(
    `/printing/templates/${encodeURIComponent(code)}/file/`,
    { responseType: 'blob' },
  )
  return data
}

export async function uploadPrintTemplate(code: string, file: File): Promise<PrintTemplate> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<PrintTemplate>(
    `/printing/templates/${encodeURIComponent(code)}/file/`,
    form,
  )
  return data
}

export async function listOperationDocuments(operationId: number): Promise<PrintDocument[]> {
  const { data } = await api.get<PrintDocument[]>(
    `/printing/operations/${operationId}/documents/`,
  )
  return data
}

export async function downloadPrintDocument(documentId: number): Promise<Blob> {
  const { data } = await api.get<Blob>(`/printing/documents/${documentId}/file/`, {
    responseType: 'blob',
  })
  return data
}
