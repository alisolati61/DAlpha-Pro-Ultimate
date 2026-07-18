from src.backtesting.walk_forward import (
    WalkForward,
    WalkForwardWindow,
)


def test_empty():

    wf = WalkForward()

    result = wf.generate([])

    assert result == []


def test_window_generation():

    wf = WalkForward()

    data = list(range(100))

    windows = wf.generate(data)

    assert len(windows) > 0

    assert isinstance(
        windows[0],
        WalkForwardWindow,
    )


def test_train_before_test():

    wf = WalkForward()

    windows = wf.generate(
        list(range(100)),
    )

    first = windows[0]

    assert first.train_end == first.test_start


def test_window_types():

    wf = WalkForward()

    window = wf.generate(
        list(range(100)),
    )[0]

    assert isinstance(window.train_start, int)

    assert isinstance(window.train_end, int)

    assert isinstance(window.test_start, int)

    assert isinstance(window.test_end, int)


def test_multiple_windows():

    wf = WalkForward()

    windows = wf.generate(
        list(range(1000)),
    )

    assert len(windows) > 1


def test_custom_sizes():

    wf = WalkForward()

    windows = wf.generate(

        list(range(500)),

        train_size=0.6,

        test_size=0.2,

        step=0.2,

    )

    assert len(windows) > 0