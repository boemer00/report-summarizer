"""Ensure PDF-export related interfaces exist."""


def test_report_generator_has_pdf_method():
    from src.summarization.report_generator import ReportGenerator

    rg = ReportGenerator()
    assert hasattr(rg, "save_report_pdf")


def test_drive_client_has_upload_file():
    from src.extractors.drive_client import DriveClient

    dc = DriveClient.__new__(DriveClient)  # avoid building service
    assert hasattr(DriveClient, "upload_file")
