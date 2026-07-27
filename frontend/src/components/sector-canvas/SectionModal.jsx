import { useState, useEffect } from 'react';
import { Modal } from './Modal';

/**
 * SectionModal — Create/edit a canvas section.
 *
 * Props:
 *   isOpen: bool
 *   editSection: { id, title, description, icon } | null (null = create mode)
 *   onSave: ({ id?, title, description, icon }) => void
 *   onClose: () => void
 */
export function SectionModal({ isOpen, editSection, onSave, onClose }) {
  var [title, setTitle] = useState('');
  var [description, setDescription] = useState('');
  var [icon, setIcon] = useState('');

  // Populate form when editSection changes
  useEffect(function () {
    if (isOpen) {
      setTitle(editSection ? editSection.title || '' : '');
      setDescription(editSection ? editSection.description || '' : '');
      setIcon(editSection ? editSection.icon || '' : '');
    }
  }, [isOpen, editSection]);

  function handleSave() {
    var trimmedTitle = title.trim();
    if (!trimmedTitle) {
      alert('Please enter a section title');
      return;
    }
    onSave({
      id: editSection ? editSection.id : undefined,
      title: trimmedTitle,
      description: description.trim() || null,
      icon: icon.trim() || null,
    });
  }

  var isEdit = editSection !== null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Edit Section' : 'Create New Section'}
      size="modal-dialog-centered"
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={handleSave}>
            <i className="bi bi-check-circle" />{' '}
            {isEdit ? 'Update Section' : 'Create Section'}
          </button>
        </>
      }
    >
      <div className="mb-3">
        <label className="form-label">Section Title *</label>
        <input
          type="text"
          className="form-control"
          placeholder="e.g., Key Themes, Risks & Challenges"
          value={title}
          onChange={function (e) { setTitle(e.target.value); }}
          autoFocus
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Description (optional)</label>
        <textarea
          className="form-control"
          rows="2"
          placeholder="Brief description of this section"
          value={description}
          onChange={function (e) { setDescription(e.target.value); }}
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Icon (optional)</label>
        <input
          type="text"
          className="form-control"
          placeholder="e.g., \u{1F4A1}, \u{1F3AF}, \u{26A0}\u{FE0F}"
          value={icon}
          onChange={function (e) { setIcon(e.target.value); }}
        />
        <small className="text-muted">Add an emoji or leave blank</small>
      </div>
    </Modal>
  );
}
