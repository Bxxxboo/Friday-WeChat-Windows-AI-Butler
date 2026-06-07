from friday.single_instance import ensure_single_instance

if __name__ == "__main__":
    ensure_single_instance()
    from friday.desktop import main

    main()
