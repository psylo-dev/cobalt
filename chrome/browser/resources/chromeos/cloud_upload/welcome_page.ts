// Copyright 2022 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import 'chrome://resources/cr_elements/cr_button/cr_button.js';

import {BaseSetupPageElement, CANCEL_SETUP_EVENT, NEXT_PAGE_EVENT} from './base_setup_page.js';
import {getTemplate} from './welcome_page.html.js';

/**
 * The WelcomePageElement represents the first page in the setup flow.
 */
export class WelcomePageElement extends BaseSetupPageElement {
  private isOfficeWebAppInstalled = false;
  private isOdfsMounted = false;

  constructor() {
    super();
  }

  override connectedCallback(): void {
    super.connectedCallback();

    this.innerHTML = getTemplate();

    const description = this.querySelector('#description') as HTMLElement;
    const actionButton = this.querySelector('.action-button') as HTMLElement;
    const cancelButton = this.querySelector('.cancel-button') as HTMLElement;

    const installOfficeWebAppDescription = 'Install Microsoft 365';
    const installOdfsDescription = 'Connect to Microsoft OneDrive';
    const moveFilesDescription =
        'Files will move to OneDrive when opening in Microsoft 365';
    const zeroStepActionButtonText = 'Set up';


    if (this.isOfficeWebAppInstalled && this.isOdfsMounted) {
      description.innerText = moveFilesDescription;
      actionButton.innerText = zeroStepActionButtonText;
    } else {
      const ul = document.createElement('ul');
      if (!this.isOfficeWebAppInstalled) {
        const installOfficeWebAppElement = document.createElement('li');
        installOfficeWebAppElement.innerText = installOfficeWebAppDescription;
        ul.appendChild(installOfficeWebAppElement);
      }
      if (!this.isOdfsMounted) {
        const installOdfsElement = document.createElement('li');
        installOdfsElement.innerText = installOdfsDescription;
        ul.appendChild(installOdfsElement);
      }
      const moveFilesElement = document.createElement('li');
      moveFilesElement.innerText = moveFilesDescription;
      ul.appendChild(moveFilesElement);
      description.appendChild(ul);
    }

    actionButton.addEventListener('click', this.onActionButtonClick);
    cancelButton.addEventListener('click', this.onCancelButtonClick);
  }

  setInstalled(isOfficeWebAppInstalled: boolean, isOdfsMounted: boolean) {
    this.isOfficeWebAppInstalled = isOfficeWebAppInstalled;
    this.isOdfsMounted = isOdfsMounted;
  }

  private onActionButtonClick() {
    this.dispatchEvent(
        new CustomEvent(NEXT_PAGE_EVENT, {bubbles: true, composed: true}));
  }

  private onCancelButtonClick() {
    this.dispatchEvent(
        new CustomEvent(CANCEL_SETUP_EVENT, {bubbles: true, composed: true}));
  }
}

customElements.define('welcome-page', WelcomePageElement);
