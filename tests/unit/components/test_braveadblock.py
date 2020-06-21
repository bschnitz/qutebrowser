# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

import pathlib
import logging
import csv
import os.path
import typing

from PyQt5.QtCore import QUrl

import pytest
import adblock

from qutebrowser.api.interceptor import ResourceType
from qutebrowser.components import braveadblock
from helpers import utils

pytestmark = pytest.mark.usefixtures("qapp")

OKAY_URLS = [
    (
        "https://qutebrowser.org/icons/qutebrowser.svg",
        "https://qutebrowser.org",
        ResourceType.image,
    ),
    (
        "https://qutebrowser.org/doc/img/main.png",
        "https://qutebrowser.org",
        ResourceType.image,
    ),
    (
        "https://qutebrowser.org/media/font.css",
        "https://qutebrowser.org",
        ResourceType.stylesheet,
    ),
    (
        "https://www.ruv.is/sites/default/files/styles/2000x1125/public/fr_20180719_091367_1.jpg?itok=0zTNSKKS&timestamp=1561275315",
        "https://www.ruv.is/frett/2020/04/23/today-is-the-first-day-of-summer",
        ResourceType.image,
    ),
    ("https://easylist.to/easylist/easylist.txt", None, ResourceType.main_frame),
    ("https://easylist.to/easylist/easyprivacy.txt", None, ResourceType.main_frame),
]

NOT_OKAY_URLS = [
    (
        "https://pagead2.googlesyndication.com/pcs/activeview?xai=AKAOjsvBN5MuZsVQyE7HD18bD-JjK589TD3zkugwCoLE2C5nP26WFNCQb8WwxzZTelPEHwwnhaOCsGxYc8WeFgYZLReqLYl8r9BtAQ6r83OHa04&sig=Cg0ArKJSzKMgXuVbXAD1EAE&adk=1473563476&tt=-1&bs=1431%2C473&mtos=120250,120250,120250,120250,120250&tos=120250,0,0,0,0&p=60,352,150,1080&mcvt=120250&rs=0&ht=0&tfs=5491&tls=125682&mc=1&lte=0&bas=0&bac=0&if=1&met=ie&avms=nio&exg=1&md=2&btr=0&lm=2&rst=1587887205533&dlt=226&rpt=1849&isd=0&msd=0&ext&xdi=0&ps=1431%2C7860&ss=1440%2C810&pt=-1&bin=4&deb=1-0-0-1192-5-1191-1191-0-0-0&tvt=125678&is=728%2C90&iframe_loc=https%3A%2F%2Ftpc.googlesyndication.com%2Fsafeframe%2F1-0-37%2Fhtml%2Fcontainer.html&r=u&id=osdtos&vs=4&uc=1192&upc=1&tgt=DIV&cl=1&cec=1&wf=0&cac=1&cd=0x0&itpl=19&v=20200422",
        "https://google.com",
        ResourceType.image,
    ),
    (
        "https://e.deployads.com/e/myanimelist.net",
        "https://myanimelist.net",
        ResourceType.xhr,
    ),
    (
        "https://c.amazon-adsystem.com/aax2/apstag.js",
        "https://www.reddit.com",
        ResourceType.script,
    ),
    (
        "https://c.aaxads.com/aax.js?pub=AAX763KC6&hst=www.reddit.com&ver=1.2",
        "https://www.reddit.com",
        ResourceType.script,
    ),
    (
        "https://pixel.mathtag.com/sync/img/?mt_exid=10009&mt_exuid=&mm_bnc&mm_bct&UUID=c7b65ea6-76cc-4700-b0c7-6dbcd10820ed",
        "https://damndelicious.net/2019/04/03/easy-slow-cooker-chili/",
        ResourceType.image,
    ),
]


def run_function_on_dataset(given_function):
    """Run the given function on a bunch of urls.

    In the data folder, we have a file called `adblock_dataset.tsv`, which
    contains tuples of (url, source_url, type) in each line. We give these
    to values to the given function, row by row.
    """

    def dataset_type_to_enum(type_int: int) -> ResourceType:
        """Translate the dataset's encoding of a resource type to Qutebrowser's."""
        if type_int == 0:
            return ResourceType.unknown
        elif type_int == 1:
            return ResourceType.image
        elif type_int == 2:
            return ResourceType.stylesheet
        elif type_int == 3:
            return ResourceType.media
        elif type_int == 4:
            return ResourceType.script
        elif type_int == 5:
            return ResourceType.font_resource
        elif type_int == 6:
            return ResourceType.xhr
        else:
            assert type_int == 7
            return ResourceType.sub_frame

    dataset = utils.adblock_dataset_tsv()
    reader = csv.DictReader(dataset, delimiter="\t")
    for row in reader:
        url = QUrl(row["url"])
        source_url = QUrl(row["source_url"])
        resource_type = dataset_type_to_enum(int(row["type"]))
        given_function(url, source_url, resource_type)


def assert_none_blocked(ad_blocker):
    assert_urls(ad_blocker, NOT_OKAY_URLS + OKAY_URLS, False)

    def assert_not_blocked(ad_blocker, url, source_url, resource_type):
        assert not ad_blocker._is_blocked(url, source_url, resource_type)

    run_function_on_dataset(
        lambda url, source_url, resource_type: assert_not_blocked(
            ad_blocker, url, source_url, resource_type
        )
    )


@pytest.fixture
def blocklist_invalid_utf8(tmpdir):
    dest_path = os.path.join(tmpdir, "invalid_utf8.txt")
    with open(dest_path, "wb") as f:
        f.write(b"invalidutf8\xa0")
    return QUrl.fromLocalFile(dest_path).toString()


@pytest.fixture
def easylist_easyprivacy(tmpdir):
    """Copy the easyprivacy and easylist blocklists into the given dir."""
    urls = []
    for blocklist, filename in [
        (utils.easylist_txt(), "easylist.txt"),
        (utils.easyprivacy_txt(), "easyprivacy.txt"),
    ]:
        bl_dst_path = os.path.join(tmpdir, filename)
        with open(bl_dst_path, "w", encoding="utf-8") as f:
            f.write("\n".join(list(blocklist)))
        assert os.path.isfile(bl_dst_path)
        urls.append(QUrl.fromLocalFile(bl_dst_path).toString())
    return urls


@pytest.fixture
def ad_blocker(data_tmpdir):
    return braveadblock.BraveAdBlocker(
        engine_factory=lambda: adblock.Engine([]), data_dir=pathlib.Path(data_tmpdir)
    )


def assert_urls(
    ad_blocker: braveadblock.BraveAdBlocker,
    urls: typing.Iterable[typing.Tuple[str, str, ResourceType]],
    should_be_blocked: bool,
) -> None:
    for (str_url, source_str_url, request_type) in urls:
        url = QUrl(str_url)
        source_url = QUrl(source_str_url)
        if should_be_blocked:
            assert ad_blocker._is_blocked(url, source_url, request_type)
        else:
            assert not ad_blocker._is_blocked(url, source_url, request_type)


@pytest.mark.parametrize(
    "blocking_enabled, should_be_blocked", [(True, True), (False, False)]
)
def test_blocking_enabled(
    config_stub,
    easylist_easyprivacy,
    caplog,
    ad_blocker,
    blocking_enabled,
    should_be_blocked,
):
    """Tests that the ads are blocked when the adblocker is enabled, and vice versa."""
    config_stub.val.content.blocking.adblock.lists = easylist_easyprivacy
    config_stub.val.content.blocking.adblock.enabled = blocking_enabled

    ad_blocker.adblock_update()
    while ad_blocker._in_progress:
        current_download = ad_blocker._in_progress[0]
        with caplog.at_level(logging.ERROR):
            current_download.successful = True
            current_download.finished.emit()
    assert_urls(ad_blocker, NOT_OKAY_URLS, should_be_blocked)
    assert_urls(ad_blocker, OKAY_URLS, False)


def test_adblock_cache(config_stub, easylist_easyprivacy, caplog, ad_blocker):
    config_stub.val.content.blocking.adblock.lists = easylist_easyprivacy
    config_stub.val.content.blocking.adblock.enabled = True

    for i in range(3):
        print("At cache test iteration {}".format(i))
        # Trying to read the cache before calling the update command should return
        # a log message.
        with caplog.at_level(logging.INFO):
            ad_blocker.read_cache()
        caplog.messages[-1].startswith(
            "Run :brave-adblock-update to get adblock lists."
        )

        if i == 0:
            # We haven't initialized the ad blocker yet, so we shouldn't be blocking
            # anything.
            assert_none_blocked(ad_blocker)

        # Now we initialize the adblocker.
        ad_blocker.adblock_update()
        while ad_blocker._in_progress:
            current_download = ad_blocker._in_progress[0]
            with caplog.at_level(logging.ERROR):
                current_download.successful = True
                current_download.finished.emit()

        # After initializing the the adblocker, we should start seeing ads
        # blocked.
        assert_urls(ad_blocker, NOT_OKAY_URLS, True)
        assert_urls(ad_blocker, OKAY_URLS, False)

        # After reading the cache, we should still be seeing ads blocked.
        ad_blocker.read_cache()
        assert_urls(ad_blocker, NOT_OKAY_URLS, True)
        assert_urls(ad_blocker, OKAY_URLS, False)

        # Now we remove the cache file and try all over again...
        os.remove(ad_blocker._cache_path)


def test_invalid_utf8(ad_blocker, config_stub, blocklist_invalid_utf8, caplog):
    """Test that the adblocker handles invalid utf-8 correctly."""
    config_stub.val.content.blocking.adblock.lists = [blocklist_invalid_utf8]
    config_stub.val.content.blocking.adblock.enabled = True

    with caplog.at_level(logging.INFO):
        ad_blocker.adblock_update()
    expected = "Block list is not valid utf-8"
    assert caplog.messages[-2].startswith(expected)


def test_config_changed(ad_blocker, config_stub, easylist_easyprivacy, caplog):
    """Ensure blocked-hosts resets if host-block-list is changed to None."""
    config_stub.val.content.blocking.adblock.enabled = True
    config_stub.val.content.blocking.whitelist = None

    for _ in range(2):
        # We should be blocking like normal, since the block lists are set to
        # easylist and easyprivacy.
        config_stub.val.content.blocking.adblock.lists = easylist_easyprivacy
        ad_blocker.adblock_update()
        while ad_blocker._in_progress:
            current_download = ad_blocker._in_progress[0]
            with caplog.at_level(logging.ERROR):
                current_download.successful = True
                current_download.finished.emit()
        assert_urls(ad_blocker, NOT_OKAY_URLS, True)
        assert_urls(ad_blocker, OKAY_URLS, False)

        # After setting the ad blocking lists to None, the ads should still be
        # blocked, since we haven't run `:brave-adblock-update`.
        config_stub.val.content.blocking.adblock.lists = None
        assert_urls(ad_blocker, NOT_OKAY_URLS, True)
        assert_urls(ad_blocker, OKAY_URLS, False)

        # After updating the adblocker, nothing should be blocked, since we set
        # the blocklist to None.
        ad_blocker.adblock_update()
        while ad_blocker._in_progress:
            current_download = ad_blocker._in_progress[0]
            with caplog.at_level(logging.ERROR):
                current_download.successful = True
                current_download.finished.emit()
        assert_none_blocked(ad_blocker)


def test_whitelist_on_dataset(config_stub, easylist_easyprivacy):
    config_stub.val.content.blocking.adblock.lists = easylist_easyprivacy
    config_stub.val.content.blocking.adblock.enabled = True
    config_stub.val.content.blocking.whitelist = None

    def assert_whitelisted(url, source_url, resource_type):
        config_stub.val.content.blocking.whitelist = None
        assert not braveadblock._is_whitelisted_url(url)
        config_stub.val.content.blocking.whitelist = []
        assert not braveadblock._is_whitelisted_url(url)
        whitelist_url = url.toString(QUrl.RemovePath) + "/*"
        config_stub.val.content.blocking.whitelist = [whitelist_url]
        assert braveadblock._is_whitelisted_url(url)

    run_function_on_dataset(assert_whitelisted)


def test_blocklists_are_whitelisted(config_stub, easylist_easyprivacy):
    blocklist_urls = [url for url, _s_url, _type in NOT_OKAY_URLS]
    config_stub.val.content.blocking.adblock.lists = (
        easylist_easyprivacy + blocklist_urls
    )
    config_stub.val.content.blocking.adblock.enabled = True
    config_stub.val.content.blocking.whitelist = None

    for url in blocklist_urls:
        assert braveadblock._is_whitelisted_url(QUrl(url))
