from django.urls import include, path

from . import views

app_name = "gregor_anvil"


research_center_patterns = (
    [
        path("<int:pk>", views.ResearchCenterDetail.as_view(), name="detail"),
        path("", views.ResearchCenterList.as_view(), name="list"),
    ],
    "research_centers",
)

partner_group_patterns = (
    [
        path("<int:pk>", views.PartnerGroupDetail.as_view(), name="detail"),
        path("", views.PartnerGroupList.as_view(), name="list"),
    ],
    "partner_groups",
)

consent_group_patterns = (
    [
        path("<int:pk>", views.ConsentGroupDetail.as_view(), name="detail"),
        path("", views.ConsentGroupList.as_view(), name="list"),
    ],
    "consent_groups",
)

upload_cycle_patterns = (
    [
        path("<int:slug>/", views.UploadCycleDetail.as_view(), name="detail"),
        path("new/", views.UploadCycleCreate.as_view(), name="new"),
        path("<int:slug>/update/", views.UploadCycleUpdate.as_view(), name="update"),
        path("", views.UploadCycleList.as_view(), name="list"),
    ],
    "upload_cycles",
)

workspace_report_patterns = (
    [
        path("workspaces/", views.WorkspaceReport.as_view(), name="workspace"),
    ],
    "reports",
)

upload_workspace_sharing_audit_patterns = (
    [
        path("all/", views.UploadWorkspaceSharingAudit.as_view(), name="all"),
        path(
            "resolve/<slug:billing_project_slug>/<slug:workspace_slug>/<slug:managed_group_slug>/",
            views.UploadWorkspaceSharingAuditResolve.as_view(),
            name="resolve",
        ),
        path(
            "upload_cycle/<int:cycle>/",
            views.UploadWorkspaceSharingAuditByUploadCycle.as_view(),
            name="by_upload_cycle",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/",
            views.UploadWorkspaceSharingAuditByWorkspace.as_view(),
            name="by_upload_workspace",
        ),
    ],
    "sharing",
)

upload_workspace_auth_domain_audit_patterns = (
    [
        path("all/", views.UploadWorkspaceAuthDomainAudit.as_view(), name="all"),
        path(
            "resolve/<slug:billing_project_slug>/<slug:workspace_slug>/<slug:managed_group_slug>/",
            views.UploadWorkspaceAuthDomainAuditResolve.as_view(),
            name="resolve",
        ),
        path(
            "upload_cycle/<int:cycle>/",
            views.UploadWorkspaceAuthDomainAuditByUploadCycle.as_view(),
            name="by_upload_cycle",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/",
            views.UploadWorkspaceAuthDomainAuditByWorkspace.as_view(),
            name="by_upload_workspace",
        ),
    ],
    "auth_domains",
)

upload_workspace_audit_patterns = (
    [
        path("sharing/", include(upload_workspace_sharing_audit_patterns)),
        path("auth_domain/", include(upload_workspace_auth_domain_audit_patterns)),
    ],
    "upload_workspaces",
)

combined_workspace_sharing_audit_patterns = (
    [
        path("all/", views.CombinedConsortiumDataWorkspaceSharingAudit.as_view(), name="all"),
        path(
            "resolve/<slug:billing_project_slug>/<slug:workspace_slug>/<slug:managed_group_slug>/",
            views.CombinedConsortiumDataWorkspaceSharingAuditResolve.as_view(),
            name="resolve",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/",
            views.CombinedConsortiumDataWorkspaceSharingAuditByWorkspace.as_view(),
            name="by_workspace",
        ),
    ],
    "sharing",
)

combined_workspace_auth_domain_audit_patterns = (
    [
        path("all/", views.CombinedConsortiumDataWorkspaceAuthDomainAudit.as_view(), name="all"),
        path(
            "resolve/<slug:billing_project_slug>/<slug:workspace_slug>/<slug:managed_group_slug>/",
            views.CombinedConsortiumDataWorkspaceAuthDomainAuditResolve.as_view(),
            name="resolve",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/",
            views.CombinedConsortiumDataWorkspaceAuthDomainAuditByWorkspace.as_view(),
            name="by_workspace",
        ),
    ],
    "auth_domains",
)

combined_workspace_audit_patterns = (
    [
        path("sharing/", include(combined_workspace_sharing_audit_patterns)),
        path("auth_domain/", include(combined_workspace_auth_domain_audit_patterns)),
    ],
    "combined_workspaces",
)

dcc_processed_data_workspace_sharing_audit_patterns = (
    [
        path("all/", views.DCCProcessedDataWorkspaceSharingAudit.as_view(), name="all"),
        path(
            "resolve/<slug:billing_project_slug>/<slug:workspace_slug>/<slug:managed_group_slug>/",
            views.DCCProcessedDataWorkspaceSharingAuditResolve.as_view(),
            name="resolve",
        ),
        path(
            "upload_cycle/<int:cycle>/",
            views.DCCProcessedDataWorkspaceSharingAuditByUploadCycle.as_view(),
            name="by_upload_cycle",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/",
            views.DCCProcessedDataWorkspaceSharingAuditByWorkspace.as_view(),
            name="by_workspace",
        ),
    ],
    "sharing",
)

dcc_processed_data_workspace_auth_domain_audit_patterns = (
    [
        path("all/", views.DCCProcessedDataWorkspaceAuthDomainAudit.as_view(), name="all"),
        # path(
        #     "resolve/<slug:billing_project_slug>/<slug:workspace_slug>/<slug:managed_group_slug>/",
        #     views.DCCProcessedDataWorkspaceAuthDomainAuditResolve.as_view(),
        #     name="resolve",
        # ),
        path(
            "upload_cycle/<int:cycle>/",
            views.DCCProcessedDataWorkspaceAuthDomainAuditByUploadCycle.as_view(),
            name="by_upload_cycle",
        ),
        path(
            "<slug:billing_project_slug>/<slug:workspace_slug>/",
            views.DCCProcessedDataWorkspaceAuthDomainAuditByWorkspace.as_view(),
            name="by_workspace",
        ),
    ],
    "auth_domains",
)

dcc_processed_data_workspace_audit_patterns = (
    [
        path("sharing/", include(dcc_processed_data_workspace_sharing_audit_patterns)),
        path("auth_domain/", include(dcc_processed_data_workspace_auth_domain_audit_patterns)),
    ],
    "dcc_processed_data_workspaces",
)

audit_patterns = (
    [
        path("upload_workspaces/", include(upload_workspace_audit_patterns)),
        path("combined_workspaces/", include(combined_workspace_audit_patterns)),
        path("dcc_processed_data_workspaces/", include(dcc_processed_data_workspace_audit_patterns)),
    ],
    "audit",
)

urlpatterns = [
    # path("", views.Index.as_view(), name="index"),
    path("research_centers/", include(research_center_patterns)),
    path("partner_groups", include(partner_group_patterns)),
    path("consent_groups/", include(consent_group_patterns)),
    path("upload_cycles/", include(upload_cycle_patterns)),
    path("reports/", include(workspace_report_patterns)),
    path("audit/", include(audit_patterns)),
]
