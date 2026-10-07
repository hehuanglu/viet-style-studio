const cancelBtn = document.getElementById("cancel-request");
if (cancelBtn) {
  cancelBtn.addEventListener("click", (e) => {
    e.stopImmediatePropagation();
    const modal = document.getElementById("cancel-confirm-modal");
    if (modal) modal.showModal();
  });
}

const resumeBtn = document.getElementById("resume-request");
if (resumeBtn) {
  resumeBtn.addEventListener("click", () => {
    const modal = document.getElementById("cancel-confirm-modal");
    if (modal) modal.close();
  });
}

const confirmBtn = document.getElementById("confirm-cancel-request");
if (confirmBtn) {
  confirmBtn.addEventListener("click", async () => {
    if (!activeId) return;
    confirmBtn.disabled = true;
    try {
      await api(`/requests/${activeId}/cancel`, { method: "POST", body: "{}" });
      const modal = document.getElementById("cancel-confirm-modal");
      if (modal) modal.close();
      await refreshJob();
    } catch (error) {
      showRequestError(error);
    } finally {
      confirmBtn.disabled = false;
    }
  });
}
