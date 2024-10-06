/** @odoo-module **/

import {useService} from "@web/core/utils/hooks";
import {onWillStart, useState} from "@odoo/owl";

odoo.define('pv_config.ProductTemplateAttributeLineExtend', [
    '@web/core/utils/patch',
    '@sale_product_configurator/js/product_template_attribute_line/product_template_attribute_line'
], function (require) {
    const {patch} = require('@web/core/utils/patch');
    const ProductTemplateAttributeLine = require('@sale_product_configurator/js/product_template_attribute_line/product_template_attribute_line');
    const ProductConfiguratorDialog = require('@sale_product_configurator/js/product_configurator_dialog/product_configurator_dialog');
    document.initialized = [];

    if (ProductConfiguratorDialog && ProductConfiguratorDialog.ProductConfiguratorDialog && ProductConfiguratorDialog.ProductConfiguratorDialog.prototype) {
        const parentSetup = ProductConfiguratorDialog.ProductConfiguratorDialog.prototype.setup;

        patch(ProductConfiguratorDialog.ProductConfiguratorDialog.prototype, {
            setup() {
                document.productTemplateLines = [];
                document.selected_header_id = -1;
                document.pcd = this;
                parentSetup.call(this);
            }
        });
    }

    if (ProductTemplateAttributeLine && ProductTemplateAttributeLine.ProductTemplateAttributeLine && ProductTemplateAttributeLine.ProductTemplateAttributeLine.prototype) {
        const parentMethodGetPTAVTemplate = ProductTemplateAttributeLine.ProductTemplateAttributeLine.prototype.getPTAVTemplate;
        const parentMethodUpdateSelectedPTAV = ProductTemplateAttributeLine.ProductTemplateAttributeLine.prototype.updateSelectedPTAV;
        patch(ProductTemplateAttributeLine.ProductTemplateAttributeLine.prototype, {
            setup() {
                document.productTemplateLines.push(this);

                this.rpc = useService("rpc");

                this.state = useState({
                    is_header: false,
                    valid_configuration_attribute: {}
                });

                this.clearSelection = async () => {
                    this.props.selected_attribute_value_ids = [];
                    const pcd = document.pcd;
                    const product = pcd._findProduct(this.props.productTmplId);
                    if (product) {
                        product.attribute_lines.find(ptal => ptal.id === this.props.id).selected_attribute_value_ids = [];
                        const updatedValues = await pcd._updateCombination(product, product.quantity);
                        Object.assign(product, updatedValues);
                    }
                }

                this.loadValues = () => {
                    if (document.selected_header_id === -1) {
                        return;
                    }
                    if (this.state.is_header) {
                        return;
                    }

                    this.clearSelection();

                    for (const value of this.props.attribute_values) {
                        this.rpc('/pv_config/get_ptav_is_valid', {
                            ptav_id: value.id,
                            selected_header_value_id: document.selected_header_id
                        }).then((is_valid) => {
                            this.state.valid_configuration_attribute[value.id] = is_valid;
                        });
                    }
                };
                onWillStart(() => {
                    this.rpc('/pv_config/get_ptal_is_header', {
                        product_template_id: this.props.productTmplId,
                        ptal_id: this.props.id
                    }).then((is_header) => {
                        this.state.is_header = is_header;
                        if (this.state.is_header && this.props.selected_attribute_value_ids.length > 0) {
                            document.selected_header_id = this.props.selected_attribute_value_ids[0];
                        }
                        this.loadAllValues();
                    });
                });
            },
            loadAllValues() {
                for (const line of document.productTemplateLines) {
                    line.loadValues();
                }
            },
            updateSelectedPTAV(event) {
                if (this.state.is_header) {
                    document.selected_header_id = event.target.value;
                }
                this.loadAllValues();
                return parentMethodUpdateSelectedPTAV.apply(this, arguments);
            },
            getPTAVTemplate() {
                const template = parentMethodGetPTAVTemplate.apply(this, arguments);
                if (template === 'saleProductConfigurator.ptav-radio') {
                    return 'pv_config.ptav-radio-extend';
                }
                return template;
            },
            getPTAVIsInvalid(ptav_id) {
                if (this.state.is_header) {
                    return false;
                }
                return this.state.valid_configuration_attribute[ptav_id] === false;
            }
        });
    }
});
