import type { Dataset } from '../api/types'

interface Props {
  datasets: Dataset[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function DatasetPicker({ datasets, selectedId, onSelect }: Props) {
  return (
    <div className="dataset-picker">
      <div className="sidebar-title">Датасеты</div>
      <ul className="dataset-list">
        {datasets.map((d) => (
          <li key={d.campaign_id}>
            <button
              className={`dataset-item ${d.campaign_id === selectedId ? 'selected' : ''}`}
              onClick={() => onSelect(d.campaign_id)}
            >
              <span className={`health-dot ${d.healthy ? 'ok' : 'bad'}`} />
              <span className="dataset-name">{d.name}</span>
              <span className={`health-tag ${d.healthy ? 'ok' : 'bad'}`}>
                {d.healthy ? 'healthy' : 'issues'}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
