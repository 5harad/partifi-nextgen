export type OrientationOption = {
  degrees: number
  orientation: 'portrait' | 'landscape'
  preview_url: string
}

export type OrientationDataResponse = {
  private_id: string
  score_orientation: 'portrait' | 'landscape'
  current_rotation_degrees: number
  current_orientation: 'portrait' | 'landscape'
  rotation_options: OrientationOption[]
  reimport_in_progress: boolean
  reimport_progress: number
  reimport_error: string | null
  reimport_error_message: string | null
}
