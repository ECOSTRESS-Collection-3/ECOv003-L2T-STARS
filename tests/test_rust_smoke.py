def test_stars_rust_extension_import_and_smoke():
    import ECOv003_L2T_STARS._stars_rust as stars_rust

    status = stars_rust.smoke_test()
    assert isinstance(status, str)
    assert "_stars_rust active" in status
